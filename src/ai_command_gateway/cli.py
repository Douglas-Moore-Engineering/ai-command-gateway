"""Local command-line interface. All execution outcomes are mock-only."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import sys
import uuid

from . import __version__


def read_json(path: Path):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"Non-finite JSON number: {value}")
        return parsed

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    if path.stat().st_size > 1_000_000:
        raise ValueError("Request exceeds the 1 MB local input limit")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant,
                      parse_float=finite_float, object_pairs_hook=unique_keys)


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False))


def parser():
    result = argparse.ArgumentParser(description="AI Command Gateway; offline by default, mock execution only")
    result.add_argument("--version", action="version", version=__version__)
    commands = result.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile", help="Hash and profile the five supplied datasets")
    profile.add_argument("--input-dir", type=Path, required=True)
    profile.add_argument("--output-dir", type=Path, default=Path("outputs/profiles"))
    qualification = commands.add_parser("qualify", help="Verify source identity and analyze timestamp quality without joining clocks")
    qualification.add_argument("--input-dir", type=Path, required=True)
    qualification.add_argument("--output-dir", type=Path, default=Path("outputs/qualification"))
    qualification.add_argument("--inventory", type=Path, default=Path("data/lineage/source-inventory.json"))
    catalog = commands.add_parser("catalog", help="Build a controlled observation catalog for local retrieval")
    catalog.add_argument("--profile", type=Path, default=Path("outputs/profiles/dataset-profile.json"))
    catalog.add_argument("--inventory", type=Path, default=Path("data/lineage/source-inventory.json"))
    catalog.add_argument("--output-dir", type=Path, default=Path("outputs/advice"))
    advice = commands.add_parser("advise", help="Retrieve cited dataset observations locally; no equipment recommendations")
    advice.add_argument("--question", required=True)
    advice.add_argument("--catalog", type=Path, default=Path("outputs/advice/evidence-catalog.json"))
    advice.add_argument("--source", choices=("S1", "S2", "S3"))
    advice.add_argument("--limit", type=int, default=3)
    advice.add_argument("--provider", choices=("offline", "openai"), default="offline",
                        help="Explicitly opt in to the hosted adapter; default stays offline")
    advice.add_argument("--dry-run", action="store_true", help="Preview the OpenAI request without sending it")
    advice.add_argument("--model", help="OpenAI model ID; default gpt-6.1-sol")
    advice.add_argument("--timeout", type=float, help="Provider socket timeout in seconds (1-60); default 30")
    advice.add_argument("--max-output-tokens", type=int, help="Output/reasoning token cap (256-4096); default 2048")
    evaluation = commands.add_parser("eval-advice", help="Run the frozen local retrieval/abstention regression casebook")
    evaluation.add_argument("--catalog", type=Path, default=Path("outputs/advice/evidence-catalog.json"))
    evaluation.add_argument("--cases", type=Path, default=Path("data/evaluation/advice-cases-v1.json"))
    evaluation.add_argument("--output-dir", type=Path, default=Path("outputs/advice-evaluation"))
    replay = commands.add_parser("replay", help="Exercise the qualification gate with historical S1 observations")
    replay.add_argument("--input-dir", type=Path, required=True)
    replay.add_argument("--output-dir", type=Path, default=Path("outputs/replay"))
    replay.add_argument("--limit", type=int, default=20)
    replay.add_argument("--policy", type=Path, default=Path("config/policies/unqualified-policy.json"))
    replay.add_argument("--db", type=Path, default=Path("outputs/replay/audit.sqlite3"))
    demo = commands.add_parser("demo", help="Run synthetic allow/block/escalate and approval/replay examples")
    demo.add_argument("--db", type=Path, default=Path("outputs/demo/audit.sqlite3"))
    demo.add_argument("--policy", type=Path, default=Path("config/policies/demo-policy.json"))
    demo.add_argument("--request", type=Path, default=Path("data/samples/demo-request.json"))
    for name in ("evaluate", "approve", "execute", "audit"):
        item = commands.add_parser(name)
        item.add_argument("--db", type=Path, default=Path("outputs/local/audit.sqlite3"))
        item.add_argument("--policy", type=Path, default=Path("config/policies/unqualified-policy.json"))
        if name != "audit":
            item.add_argument("--request", type=Path, required=True)
        if name in ("approve", "execute"):
            item.add_argument("--actor", required=True, help="Local demo actor label; not authenticated identity")
        if name == "execute":
            item.add_argument("--approval-id", required=True)
    return result


def run_demo(args):
    from .gateway import Gateway

    gateway = Gateway(args.db, args.policy)
    request = read_json(args.request)
    if (type(request) is not dict or type(request.get("proposal")) is not dict
            or type(request.get("state")) is not dict):
        raise ValueError("Demo fixture must contain proposal and state objects")
    request["proposal"]["id"] = f"synthetic-demo-{uuid.uuid4().hex}"
    request["state"]["observed_at"] = datetime.now(timezone.utc).isoformat()
    allow = gateway.evaluate(request)
    outside_limit = deepcopy(request)
    outside_limit["proposal"]["value"] = 1_000_000
    block = gateway.evaluate(outside_limit)
    no_evidence = deepcopy(request)
    no_evidence["proposal"]["source_refs"] = []
    escalate = gateway.evaluate(no_evidence)
    approval = gateway.approve(request, actor="local-demo-operator")
    execution = replay = None
    if approval.get("approval_id"):
        execution = gateway.execute(request, approval["approval_id"], actor="local-demo-operator")
        replay = gateway.execute(request, approval["approval_id"], actor="local-demo-operator")
    checks = {
        "synthetic_in_range_allowed": allow["decision"] == "allow",
        "synthetic_out_of_range_blocked": block["decision"] == "block",
        "missing_evidence_escalated": escalate["decision"] == "escalate",
        "approved_mock_executed": bool(execution and execution["decision"] == "allow"),
        "approval_replay_blocked": bool(replay and replay["decision"] == "block"),
    }
    emit({"scope": "synthetic offline demonstration; no physical safety or authentication claim",
          "checks": checks, "evaluate": allow, "block": block, "escalate": escalate,
          "approval": approval, "execution": execution, "replay": replay,
          "audit_db": str(args.db)})
    return 0 if all(checks.values()) else 1


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "profile":
            from .datasets import profile_sources
            report = profile_sources(args.input_dir, args.output_dir)
            emit(report)
            # The report remains available for partial/missing input investigations.
            complete = report.get("inspection_summary", {}).get("status") == "complete"
            return 0 if complete and report.get("files") and all(item.get("status") == "profiled" for item in report["files"]) else 1
        if args.command == "qualify":
            from .qualification import qualify_sources
            report = qualify_sources(args.input_dir, args.output_dir, args.inventory)
            emit(report)
            return 0 if report.get("inspection_summary", {}).get("status") == "complete" else 1
        if args.command == "catalog":
            from .evidence import build_catalog
            report = build_catalog(args.profile, args.inventory, args.output_dir)
            emit(report)
            return 0
        if args.command == "advise":
            if args.provider == "openai":
                from .model_advisor import advise_with_model
                from .openai_transport import OpenAIConfig
                options = {key: value for key, value in {
                    "model": args.model, "timeout_seconds": args.timeout,
                    "max_output_tokens": args.max_output_tokens}.items() if value is not None}
                report = advise_with_model(args.question, args.catalog, source_id=args.source,
                                           limit=args.limit, config=OpenAIConfig(**options), dry_run=args.dry_run)
                emit(report)
                response = report["response"]
                if report["model"]["status"] == "rejected" or response.get("reason_code") in {
                        "catalog_unverified", "invalid_question", "invalid_filter"}:
                    return 1
                if report["model"]["status"] == "fallback":
                    return 3
                return 0 if response.get("response_type") == "observation" else 2
            if args.dry_run or any(value is not None for value in (args.model, args.timeout, args.max_output_tokens)):
                raise ValueError("Provider options require --provider openai")
            from .advisor import advise
            report = advise(args.question, args.catalog, source_id=args.source, limit=args.limit)
            emit(report)
            if report.get("reason_code") in {"catalog_unverified", "invalid_question", "invalid_filter"}:
                return 1
            return 0 if report.get("response_type") == "observation" else 2
        if args.command == "eval-advice":
            from .advice_evaluation import evaluate_advice
            report = evaluate_advice(args.catalog, args.cases, args.output_dir)
            emit(report)
            return 0 if report.get("all_cases_passed") else 1
        if args.command == "replay":
            from .replay import replay_process
            report = replay_process(args.input_dir, args.output_dir, args.policy, args.db, args.limit)
            emit(report)
            return 0 if report["qualification_gate_exercised"] else 1
        if args.command == "demo":
            return run_demo(args)
        from .gateway import Gateway
        gateway = Gateway(args.db, args.policy)
        if args.command == "audit":
            emit(gateway.audit_records())
            return 0
        request = read_json(args.request)
        if args.command == "evaluate":
            result = gateway.evaluate(request)
        elif args.command == "approve":
            result = gateway.approve(request, args.actor)
        else:
            result = gateway.execute(request, args.approval_id, args.actor)
        emit(result)
        return 0 if result["decision"] == "allow" else 2
    except (OSError, ValueError, RuntimeError, ImportError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "outcome": "no_mock_execution"}), file=sys.stderr)
        return 1
