"""Durable long-dialogue checks; literal identity is separate from answer quality."""
import hashlib
import json
from pathlib import Path
import sqlite3

from memory import public_state, empty_state
from chat_agent import render_response


def load_scenarios(path):
    scenarios = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(scenarios, list) or len(scenarios) != 2:
        raise ValueError("Require exactly two long scenarios")
    ids = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "goal", "constraints", "clarifications", "terms", "turns"}:
            raise ValueError("Invalid scenario fields")
        if not isinstance(scenario["id"], str) or not scenario["id"] or scenario["id"] in ids:
            raise ValueError("Scenario IDs must be nonempty and unique")
        ids.add(scenario["id"])
        if not isinstance(scenario["goal"], str) or not scenario["goal"]:
            raise ValueError("Scenario needs an explicit goal")
        for field in ("constraints", "clarifications"):
            if not isinstance(scenario[field], list) or not scenario[field] or any(not isinstance(v, str) or not v for v in scenario[field]):
                raise ValueError("Scenario needs nonempty memory expectations")
        if not isinstance(scenario["terms"], dict) or not scenario["terms"] or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in scenario["terms"].items()):
            raise ValueError("Scenario needs literal term definitions")
        if not isinstance(scenario["turns"], list) or not 10 <= len(scenario["turns"]) <= 15:
            raise ValueError("Each scenario needs 10–15 user turns")
        for row in scenario["turns"]:
            if not isinstance(row, dict) or set(row) != {"message", "expected_source"} or any(
                    not isinstance(v, str) or not v.strip() for v in row.values()) or len(row["message"]) > 4000:
                raise ValueError("Each turn needs a bounded question and expected source")
    return scenarios


def check_sources(result):
    """Check source IDs, quote offsets, claim identity and the whole rendered answer."""
    try:
        selected = {row["chunk_id"]: row for row in result["retrieval"]["sources"]}
        sources = {row["id"]: row for row in result["sources"]}
        quotes, claims = result["quotes"], result["claims"]
        if result["status"] != "answered" or not sources or not quotes or len(sources) != len(result["sources"]):
            return False
        if list(sources) != list(range(1, len(sources) + 1)) or len(claims) != len(quotes):
            return False
        used, statements = set(), []
        for source in sources.values():
            hit = selected.get(source["chunk_id"])
            if not hit or source["cosine"] != hit["score"] or any(source[key] != hit[key] for key in ("source", "section", "start_line", "end_line")):
                return False
        for claim, quote in zip(claims, quotes):
            source = sources.get(quote["source_id"])
            if not source or source["chunk_id"] != quote["chunk_id"] or claim["id"] != quote["claim_id"]:
                return False
            hit = selected[quote["chunk_id"]]
            text = quote["quote"]
            if not isinstance(text, str) or len(text.strip()) < 12 or text not in hit["text"] or claim["text"] != text:
                return False
            start = hit["start_line"] + hit["text"].count("\n", 0, hit["text"].index(text))
            if quote["start_line"] != start or quote["end_line"] != start + text.count("\n"):
                return False
            if any(quote[key] != hit[key] for key in ("source", "section")):
                return False
            ref = {k: v for k, v in quote.items() if k not in ("claim_id", "source_id")}
            if claim["citations"] != [ref] or (quote["chunk_id"], text) in used:
                return False
            used.add((quote["chunk_id"], text))
            rendered = "```python\n" + text + "\n```" if source["source"].endswith(".py") and "```" not in text else text
            separator = "\n" if rendered.rstrip().endswith(("```", "~~~")) else " "
            statements.append(rendered + separator + f"[{source['id']}]")
        return {q["source_id"] for q in quotes} == set(sources) and result["answer"] == "\n".join(statements)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def check_retrieval(result, seen):
    trace = result.get("retrieval_trace", {})
    embeds, searches = trace.get("embedding_calls", []), trace.get("search_calls", [])
    ident = trace.get("request_id")
    valid = (isinstance(ident, str) and bool(ident) and ident not in seen
             and trace.get("session_id") == result.get("session_id") and trace.get("turn_id") == result.get("turn_id")
             and bool(embeds) and bool(searches)
             and all(isinstance(row.get("queries"), list) and bool(row["queries"])
                     and row.get("vectors") == len(row["queries"]) for row in embeds)
             and sum(row.get("vectors", 0) for row in embeds) == len(searches))
    if ident:
        seen.add(ident)
    return bool(valid)


def turn_checks(result, step, scenario, before, seen):
    memory = public_state(result["task_state"])
    checks = {
        "answered": result["status"] == "answered", "fresh_retrieval": check_retrieval(result, seen),
        "source_contract": check_sources(result),
        "expected_source": any(s["source"].startswith(step["expected_source"]) for s in result["sources"]),
        "goal_retained": memory["goal"] == scenario["goal"],
        "previous_memory_preserved": all(result["task_state"][field].get(k) == value
            for field in ("constraints", "clarifications", "terms") for k, value in before[field].items()),
        "sources_rendered": "Источники / Sources:" in render_response(result),
        "no_planning_warnings": not result["conversation"]["warnings"],
        "coverage_pass": result["validation"].get("coverage_supported") is True}
    return checks


def evaluate(agent, scenarios_path, backend, restart=None, progress=None, *, ask=None,
             checkpoint=None, resume_report=None, configuration=None):
    scenarios = load_scenarios(scenarios_path)
    signature = hashlib.sha256(json.dumps(scenarios, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    configuration = configuration or {}
    kind = "process_per_turn" if ask else "store_reopen" if restart else "none"
    report = {"backend": backend, "scenario_signature": signature, "configuration": configuration,
              "run_status": "running", "details": []}
    details = report["details"]
    if resume_report is not None:
        if any(resume_report.get(key) != value for key, value in (
                ("backend", backend), ("scenario_signature", signature), ("configuration", configuration))):
            raise ValueError("Checkpoint scenarios/configuration differ; use a new output file")
        if resume_report.get("summary", {}).get("restart_kind") != kind:
            raise ValueError("Checkpoint restart mode differs")
        details.extend(resume_report.get("details", []))
        if len(details) > len(scenarios):
            raise ValueError("Invalid checkpoint scenario count")
        # Validate every saved prefix against authoritative persistent history.
        for scenario, detail in zip(scenarios, details):
            rows = detail.get("turns", [])
            history = agent.store.history(detail["session"])
            if detail["scenario"] != scenario["id"] or not len(rows) <= len(history) <= len(rows) + 1 or len(history) > len(scenario["turns"]):
                raise ValueError("Checkpoint/history mismatch; inspect history before continuing")
            for number, (row, stored, step) in enumerate(zip(rows, history, scenario["turns"]), 1):
                if row.get("number") != number or stored["question"] != step["message"] or stored["status"] == "pending":
                    raise ValueError("Checkpoint/history mismatch or interrupted pending turn")
                if row.get("result") != stored["response"]:
                    raise ValueError("Checkpoint answer differs from persistent history")
            if len(history) == len(rows) + 1:
                stored = history[-1]
                step = scenario["turns"][len(rows)]
                if stored["question"] != step["message"] or stored["status"] not in ("complete", "error"):
                    raise ValueError("Uncheckpointed turn differs or remains pending; inspect history and /recover")
                row = {"number": len(history), "checkpoint_reconciled_from_history": True}
                if stored["response"] is not None:
                    row.update(result=stored["response"], manual_review={"relevant": None, "complete": None, "goal_respected": None})
                else:
                    row.update(checks={"technical_success": False}, error=stored["error"])
                rows.append(row)
    seen = set()
    for scenario, detail in zip(scenarios, details):
        before = empty_state()
        for row, step in zip(detail["turns"], scenario["turns"]):
            if "result" in row:
                row["checks"] = turn_checks(row["result"], step, scenario, before, seen)
                before = row["result"]["task_state"]
            else:
                row["checks"] = {"technical_success": False}

    def save():
        count = sum(len(d["turns"]) for d in details)
        responses = sum("result" in row for d in details for row in d["turns"])
        report["summary"] = {"scenarios": len(details), "user_turns": count,
            "messages_including_answers": count + responses,
            "all_checks_pass": report["run_status"] == "completed" and all(
                all(d.get("checks", {}).values()) and bool(d.get("checks")) for d in details),
            "model_quality_verified": False, "manual_source_review_required": True,
            "live_ollama_used": backend == "live-ollama", "restart_kind": kind,
            "restart_after_turn": 6 if restart and not ask else None}
        if checkpoint:
            checkpoint(report)

    save()
    for index, scenario in enumerate(scenarios):
        if index == len(details):
            details.append({"scenario": scenario["id"], "session": agent.store.create("Day25 evaluation: " + scenario["id"]),
                            "checks": {}, "turns": []})
            save()
        detail = details[index]
        session, rows = detail["session"], detail["turns"]
        for number in range(len(rows) + 1, len(scenario["turns"]) + 1):
            step = scenario["turns"][number - 1]
            if progress:
                progress(f"{scenario['id']}: turn {number}/{len(scenario['turns'])}")
            if number == 7 and restart and not ask:
                restart()
            before = agent.store.get(session)["state"]
            try:
                result = (ask or agent.ask)(session, step["message"])
                checks = turn_checks(result, step, scenario, before, seen)
                rows.append({"number": number, "checks": checks, "result": result,
                             "manual_review": {"relevant": None, "complete": None, "goal_respected": None}})
            except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
                history = agent.store.history(session)
                # A failure before reservation cannot be skipped on resume.
                if len(history) != number or history[-1]["status"] != "error":
                    raise
                rows.append({"number": number, "checks": {"technical_success": False}, "error": str(error)})
            save()
        history = agent.store.history(session)
        state = public_state(agent.store.get(session)["state"])
        detail["checks"] = {
            "history_complete": len(history) == len(scenario["turns"]) and all(
                row["status"] == "complete" and row["response"] == check.get("result")
                for row, check in zip(history, rows)),
            "goal_retained": state["goal"] == scenario["goal"],
            "constraints_retained": all(v in state["constraints"].values() for v in scenario["constraints"]),
            "clarifications_retained": all(v in state["clarifications"].values() for v in scenario["clarifications"]),
            "terms_retained": all(state["terms"].get(k) == v for k, v in scenario["terms"].items()),
            "all_turn_checks_pass": all(all(row["checks"].values()) for row in rows)}
        save()
    report["run_status"] = "completed"
    save()
    return report
