"""Day 32: offline by default; network commands are restricted to GitHub Actions."""
import argparse
import json
import os
from pathlib import Path
import time

from common import (MODEL, OWNER, REPOSITORY, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS,
                    ReviewError, assert_same, check_pr, digest, dump, fail, number, sha, strict_json)
from diff_context import evidence_catalog, prepare_files
from github_api import GitHub
from groq_adapter import Groq, input_bound, pack
from reports import markdown, save, verify_report
from retrieval import retrieve
from validation import validate


def workflow_context(env, event, live=False):
    if (env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_ACTOR") != OWNER or env.get("GITHUB_TRIGGERING_ACTOR") != OWNER):
        fail("untrusted_workflow_actor")
    kind = env.get("GITHUB_EVENT_NAME")
    if kind == "workflow_dispatch":
        if env.get("GITHUB_REF") != "refs/heads/main":
            fail("untrusted_workflow_ref")
        inputs = event.get("inputs", {})
        raw_number = inputs.get("pr_number", "")
        if not isinstance(raw_number, str) or not raw_number.isascii() or not raw_number.isdecimal():
            fail("invalid_pr_number")
        pr_number, head = number(int(raw_number)), sha(inputs.get("head_sha"))
        source = sha(env.get("GITHUB_SHA"))
        if live:
            if inputs.get("confirm_one_call") not in {True, "true"}:
                fail("missing_live_confirmation")
            if env.get("GITHUB_RUN_ATTEMPT") != "1":
                fail("rerun_forbidden")
            for variable in ("DAY32_LIVE_ENABLED", "DAY32_ENVIRONMENT_CONFIRMED",
                             "DAY32_BRANCH_TRUST_CONFIRMED", "DAY32_FREE_PLAN_CONFIRMED"):
                if env.get(variable) != "true":
                    fail("live_configuration_unconfirmed")
    elif kind == "pull_request" and not live:
        if event.get("action") not in {"opened", "synchronize", "reopened"}:
            fail("unsupported_event")
        pr = event.get("pull_request", {})
        try:
            pr_number, head, source = number(pr["number"]), sha(pr["head"]["sha"]), sha(pr["base"]["sha"])
            check_pr(pr, head, source, env["GITHUB_ACTOR"])
        except (KeyError, TypeError):
            fail("invalid_pr_event")
    else:
        fail("unsupported_event")
    # The workflow supplies this from its checkout ref, never a PR input string.
    if env.get("SOURCE_REVISION") != source:
        fail("checkout_revision_mismatch")
    return pr_number, head, source


def prepare(api, pr_number, head, source, actor, root):
    pr = api.pr(pr_number)
    check_pr(pr, head, source, actor)
    if pr["number"] != pr_number:
        fail("pr_number_changed")
    rows = api.files(pr)
    current = api.pr(pr_number)
    check_pr(current, head, source, actor)
    assert_same(pr, current)
    files, omissions = prepare_files(rows)
    docs, retrieval = retrieve(root, files, source)
    context, files, docs, budget_omissions = pack(files, docs)
    omissions += budget_omissions
    retrieval["selected_chunks"] = len(docs)
    catalog = evidence_catalog(files, docs)
    return pr, context, catalog, omissions, retrieval, files


def review_result(raw, catalog, report):
    findings, rejected = validate(raw, catalog)
    report.update(findings=findings, rejected_findings=rejected)
    if rejected and not findings:
        report["status"] = "invalid_findings"
    elif rejected or report["omissions"]:
        report["status"] = "partial"
    else:
        report["status"] = "completed"


def pipeline(api, pr_number, head, source, actor, root, report, summary, generator=None, mock_raw=None):
    pr, context, catalog, omissions, retrieval, files = prepare(api, pr_number, head, source, actor, root)
    changed = sum(e["kind"] == "diff" and e["changed"] for e in catalog.values())
    report.update(pr_number=pr_number, head_sha=head, base_sha=source, source_revision=source,
                  omissions=omissions, retrieval=retrieval, catalog=catalog,
                  previous_paths={f["path"]: f["previous_path"] for f in files if f["previous_path"]},
                  selected_changed_lines=changed, selected_files=len(files))
    summary.update(input_token_upper_bound=input_bound(context), changed_files=pr["changed_files"],
                   selected_files=len(files), selected_changed_lines=changed,
                   retrieval_selected_chunks=retrieval["selected_chunks"], context_digest=digest(context))
    if not files:
        fail("no_reviewable_hunks")
    latest = api.pr(pr_number)
    check_pr(latest, head, source, actor)
    if generator is None and mock_raw is None:
        report["status"] = "preflight_ready"
        return
    if generator is not None:
        if not retrieval["selected_chunks"]:
            fail("live_requires_document_evidence")
        raw = generator.generate(context)
    else:
        raw = mock_raw
        summary["mock_generation_outputs"] = 1
    review_result(raw, catalog, report)
    latest = api.pr(pr_number)
    check_pr(latest, head, source, actor)


class FixtureGitHub:
    """No transport or credential handling in the offline CLI."""
    def __init__(self, fixture):
        self.fixture = fixture
        self.calls = 0

    def pr(self, _number):
        self.calls += 1
        return self.fixture["pr"]

    def files(self, _pr):
        self.calls += 1
        return self.fixture["files"]


def publish(api, report, expected_number, head, source, actor, run_id, run_attempt):
    verify_report(report)
    if (report.get("mode") != "live_groq" or report.get("status") not in {"completed", "partial"}
            or report.get("model") != MODEL or report.get("pr_number") != expected_number
            or report.get("head_sha") != head or report.get("source_revision") != source
            or report.get("base_sha") != source or report.get("run_id") != run_id
            or report.get("run_attempt") != run_attempt or report.get("generation_calls") != 1):
        fail("report_not_publishable")
    # The artifact is data from this run. Revalidate findings, not executable content.
    rows = [{**f, "evidence": [entry["id"] for entry in f["evidence"]]} for f in report["findings"]]
    accepted, rejected = validate(dump({"findings": rows}), report["catalog"])
    if rejected or accepted != report["findings"]:
        fail("report_findings_invalid")
    current = api.pr(expected_number)
    check_pr(current, head, source, actor)
    if current["number"] != expected_number:
        fail("pr_number_changed")
    body = markdown(report)
    if len(body.encode()) > 50000:
        fail("comment_size")
    api.comment(expected_number, body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("offline", "preflight", "live", "publish"))
    parser.add_argument("--root", type=Path, required=True, help="Trusted base checkout, or synthetic fixture root")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    started = time.monotonic()
    mode = {"offline": "offline_mock", "preflight": "github_preflight_no_generation",
            "live": "live_groq", "publish": "publication_only"}[args.command]
    env = os.environ
    report = {"schema_version": 1, "repository": REPOSITORY, "status": "error", "mode": mode,
              "model": MODEL, "findings": [], "rejected_findings": [], "omissions": [],
              "run_id": env.get("GITHUB_RUN_ID", "offline"), "run_attempt": env.get("GITHUB_RUN_ATTEMPT", "0")}
    summary = {"schema_version": 1, "mode": mode, "provider": "groq" if args.command == "live" else None,
               "model": MODEL, "generation_calls": 0, "mock_generation_outputs": 0, "network_calls": 0,
               "input_tokens": None, "output_tokens": None, "actual_billed_usd": None,
               "estimated_list_cost_usd": None, "price_snapshot_date": "2026-10-16",
               "limits": {"input_tokens_upper_bound": MAX_INPUT_TOKENS, "output_tokens": MAX_OUTPUT_TOKENS,
                          "generation_calls": 1}, "semantic_support_verified": False}
    api = generator = None
    try:
        if args.command == "offline":
            if args.fixture is None:
                fail("fixture_required")
            fixture = strict_json(args.fixture.read_text(encoding="utf-8"))
            api = FixtureGitHub(fixture)
            pr = fixture["pr"]
            pipeline(api, pr["number"], pr["head"]["sha"], pr["base"]["sha"], OWNER, args.root,
                     report, summary, mock_raw=dump(fixture["mock_review"]))
        else:
            event = strict_json(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
            pr_number, head, source = workflow_context(env, event, live=args.command in {"live", "publish"})
            report.update(pr_number=pr_number, head_sha=head, base_sha=source, source_revision=source)
            api = GitHub(env.get("GITHUB_TOKEN"))
            if args.command == "publish":
                if args.report is None:
                    fail("report_required")
                candidate = strict_json(args.report.read_text(encoding="utf-8"))
                publish(api, candidate, pr_number, head, source, OWNER,
                        env.get("GITHUB_RUN_ID"), env.get("GITHUB_RUN_ATTEMPT"))
                report["status"] = "published"
            else:
                if args.command == "live":
                    generator = Groq(env.get("GROQ_API_KEY"))
                pipeline(api, pr_number, head, source, OWNER, args.root, report, summary, generator=generator)
    except ReviewError as error:
        report.update(status="error", error=str(error))
    except Exception:
        # Avoid logging payloads, environment, paths or exception text.
        report.update(status="error", error="unexpected_technical_error")
    finally:
        if generator:
            summary.update(generator.metrics)
        summary["github_calls"] = api.calls if api and args.command != "offline" else 0
        summary["mock_github_observations"] = api.calls if api and args.command == "offline" else 0
        summary["network_calls"] = 0 if args.command == "offline" else summary["github_calls"] + summary["generation_calls"]
        summary.update(status=report["status"], error=report.get("error"), source_revision=report.get("source_revision"),
                       base_sha=report.get("base_sha"), head_sha=report.get("head_sha"),
                       total_seconds=round(time.monotonic() - started, 3))
        report["generation_calls"] = summary["generation_calls"]
        try:
            save(args.output, report, summary)
        except Exception:
            print('{"status":"error","error":"report_write_failed"}')
            return 2
    print(dump({"status": report["status"], "mode": mode, "generation_calls": summary["generation_calls"],
                "network_calls": summary["network_calls"], "error": report.get("error")}))
    return 0 if report["status"] in {"completed", "partial", "preflight_ready", "published"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
