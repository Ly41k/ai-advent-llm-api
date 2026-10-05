"""Long-dialogue contract checks, with answer quality left for source review."""
import json
from pathlib import Path

from memory import public_state
from chat_agent import render_response


def load_scenarios(path):
    scenarios = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(scenarios, list) or len(scenarios) != 2:
        raise ValueError("Require exactly two long scenarios")
    for scenario in scenarios:
        if not 10 <= len(scenario["turns"]) <= 15:
            raise ValueError("Each scenario needs 10–15 user turns")
        for row in scenario["turns"]:
            if not row.get("message") or not row.get("expected_source"):
                raise ValueError("Each turn needs a question and expected source")
    return scenarios


def check_sources(result):
    selected = {row["chunk_id"]: row for row in result["retrieval"]["sources"]}
    sources = {row["id"]: row for row in result["sources"]}
    if result["status"] != "answered" or not sources or not result["quotes"]:
        return False
    for source in sources.values():
        hit = selected.get(source["chunk_id"])
        if not hit or any(source[key] != hit[key] for key in ("source", "section", "start_line", "end_line")):
            return False
        if f"[{source['id']}]" not in result["answer"]:
            return False
    for quote in result["quotes"]:
        source = sources.get(quote["source_id"])
        if not source or source["chunk_id"] != quote["chunk_id"]:
            return False
        if quote["quote"] not in selected[quote["chunk_id"]]["text"]:
            return False
    return True


def evaluate(agent, scenarios_path, backend, restart=None, progress=None):
    scenarios = load_scenarios(scenarios_path)
    details = []
    for scenario in scenarios:
        session = agent.store.create("Day25 evaluation: " + scenario["id"])
        rows = []
        for number, step in enumerate(scenario["turns"], 1):
            if progress:
                progress(f"{scenario['id']}: turn {number}/{len(scenario['turns'])}")
            if number == 7 and restart:
                restart()
            try:
                result = agent.ask(session, step["message"])
                memory = public_state(result["task_state"])
                checks = {
                    "answered": result["status"] == "answered",
                    "fresh_retrieval": bool(result["retrieval"].get("candidates")),
                    "source_contract": check_sources(result),
                    "expected_source": any(s["source"].startswith(step["expected_source"]) for s in result["sources"]),
                    "goal_retained": memory["goal"] == scenario["goal"],
                    "sources_rendered": "Источники / Sources:" in render_response(result),
                    "no_planning_warnings": not result["conversation"]["warnings"],
                    "coverage_pass": result["validation"].get("coverage_supported") is True}
                rows.append({"number": number, "checks": checks, "result": result,
                             "manual_review": {"relevant": None, "complete": None, "goal_respected": None}})
            except (ValueError, RuntimeError, OSError) as error:
                rows.append({"number": number, "checks": {"technical_success": False}, "error": str(error)})
        state = public_state(agent.store.get(session)["state"])
        checks = {
            "history_complete": len(agent.store.history(session)) == len(scenario["turns"]),
            "goal_retained": state["goal"] == scenario["goal"],
            "constraints_retained": all(v in state["constraints"].values() for v in scenario["constraints"]),
            "clarifications_retained": all(v in state["clarifications"].values() for v in scenario["clarifications"]),
            "terms_retained": all(state["terms"].get(k) == v for k, v in scenario["terms"].items()),
            "all_turn_checks_pass": all(all(row["checks"].values()) for row in rows)}
        details.append({"scenario": scenario["id"], "session": session, "checks": checks, "turns": rows})
    return {"backend": backend, "summary": {
        "scenarios": len(details), "user_turns": sum(len(d["turns"]) for d in details),
        "messages_including_answers": sum(2 * len(d["turns"]) for d in details),
        "all_checks_pass": all(all(d["checks"].values()) for d in details),
        "model_quality_verified": False, "manual_source_review_required": True,
        "live_ollama_used": backend == "live-ollama",
        "restart_after_turn": 6 if restart else None}, "details": details}
