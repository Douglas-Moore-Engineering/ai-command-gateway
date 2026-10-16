"""Reproduce local software checks; never asserts domain or release acceptance."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

from ai_command_gateway import __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="Also inspect all sources, build/evaluate cited advice, and replay S1 qualification")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "outputs" / "verification"
    destination.mkdir(parents=True, exist_ok=True)
    commands = [
        ("tests", ["-m", "pytest", "-q", "--junitxml=outputs/verification/tests.xml"], 0, None),
        ("repository", ["scripts/check_repository.py"], 0, None),
        ("demo", ["-m", "ai_command_gateway", "demo", "--db", "outputs/verification/demo.sqlite3"], 0, None),
    ]
    if args.input_dir:
        commands.extend([
            ("profile", ["-m", "ai_command_gateway", "profile", "--input-dir", str(args.input_dir.resolve()),
                         "--output-dir", "outputs/profiles"], 0, None),
            ("qualify", ["-m", "ai_command_gateway", "qualify", "--input-dir", str(args.input_dir.resolve()),
                         "--output-dir", "outputs/qualification"], 0, None),
            ("catalog", ["-m", "ai_command_gateway", "catalog"], 0, "profile"),
            ("advice", ["-m", "ai_command_gateway", "advise", "--question",
                        "What are the minimum and maximum in_batt_state_of_charge in process_dataset.parquet?",
                        "--source", "S1"], 0, "catalog"),
            ("abstention", ["-m", "ai_command_gateway", "advise", "--question",
                            "Set the battery power to 500 kW."], 2, "catalog"),
            ("advice_evaluation", ["-m", "ai_command_gateway", "eval-advice"], 0, "catalog"),
            ("model_preview", ["-m", "ai_command_gateway", "advise", "--provider", "openai", "--dry-run",
                               "--question", "How many rows are in packets_dataset.parquet?", "--source", "S1"], 0, "catalog"),
            ("replay", ["-m", "ai_command_gateway", "replay", "--input-dir", str(args.input_dir.resolve()),
                        "--output-dir", "outputs/verification/replay", "--db", "outputs/verification/replay.sqlite3",
                        "--limit", "20"], 0, None),
        ])
    checks = []
    for name, command, expected_exit_code, dependency in commands:
        check = {"name": name, "command": ["python", *command], "expected_exit_code": expected_exit_code}
        if dependency and not any(item["name"] == dependency and item["passed"] for item in checks):
            check.update(passed=False, exit_code=None, error=f"Skipped: {dependency} failed; stale output must not be reused")
            checks.append(check)
            print(f"{name}: SKIPPED", flush=True)
            continue
        try:
            result = subprocess.run([sys.executable, *command], cwd=root, text=True, capture_output=True,
                                    encoding="utf-8", errors="replace", timeout=300)
        except (OSError, subprocess.TimeoutExpired) as exc:
            check.update(passed=False, exit_code=None, error=str(exc))
            checks.append(check)
            print(f"{name}: FAIL", flush=True)
            continue
        (destination / f"{name}.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (destination / f"{name}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        check.update(exit_code=result.returncode, passed=result.returncode == expected_exit_code)
        if name == "tests":
            check["summary"] = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "no test output"
        elif name == "repository":
            check["summary"] = result.stdout.strip()
        elif check["passed"]:
            output = json.loads(result.stdout)
            if name == "demo":
                check["checks"] = output["checks"]
            elif name == "profile":
                check["files"] = [{"source_id": item["source_id"], "filename": item["filename"],
                                   "sha256": item["sha256"], "status": item["status"]}
                                  for item in output["files"]]
                check["inspection_summary"] = output["inspection_summary"]
            elif name == "replay":
                check["rows_replayed"] = output["rows_replayed"]
                check["decisions"] = output["decisions"]
                check["qualification_gate_exercised"] = output["qualification_gate_exercised"]
            elif name == "qualify":
                check["inspection_summary"] = output["inspection_summary"]
                check["qualification"] = output["qualification"]
                check["report_sha256"] = output["report_sha256"]
                check["evidence_count"] = len(output["evidence"])
            elif name == "catalog":
                check["catalog_id"] = output["catalog_id"]
                check["content_sha256"] = output["content_sha256"]
                check["fact_count"] = len(output["facts"])
                check["authorizes_execution"] = output["authorizes_execution"]
            elif name in {"advice", "abstention"}:
                check["response"] = output
            elif name == "advice_evaluation":
                check["evaluation"] = {key: value for key, value in output.items() if key != "cases"}
                check["case_results"] = [{"id": item["id"], "passed": item["passed"], "failures": item["failures"]}
                                         for item in output["cases"]]
            elif name == "model_preview":
                check["model"] = output["model"]
                check["response_type"] = output["response"]["response_type"]
                check["request_preview_included"] = output["request_preview"] is not None
                check["passed"] = (output["model"]["status"] == "dry_run"
                                   and output["model"]["attempted"] is False
                                   and output["response"]["can_execute"] is False
                                   and check["request_preview_included"])
        checks.append(check)
        print(f"{name}: {'PASS' if check['passed'] else 'FAIL'}", flush=True)
    source_paths = [root / "pyproject.toml", root / "requirements-dev.lock", Path(__file__),
                    root / "requirements-runtime.lock", root / "requirements-azure.in",
                    root / "requirements-azure.lock", root / "Dockerfile", root / ".dockerignore"]
    for folder, extension in (("src", "*.py"), ("tests", "*.py"), ("tests/fixtures", "*.json"),
                              ("config", "*.json"), ("data/contracts", "*.json"),
                              ("data/evaluation", "*.json"), ("data/lineage", "*.json"),
                              ("infra", "*.bicep"), ("infra", "*.json"),
                              ("scripts", "*.ps1"), ("scripts", "*.py"), (".azure", "*.json")):
        source_paths.extend((root / folder).rglob(extension))
    source_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(set(source_paths))}
    report = {
        "version": __version__, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "local software, extractive advice, mocked provider/storage boundaries and source-observation verification; no live Azure/model or domain acceptance claim",
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {name: importlib.metadata.version(name) for name in ("pyarrow", "scipy", "numpy", "h5py", "pytest")},
        "optional_dependencies": {},
        "checks": checks, "all_checks_passed": all(check["passed"] for check in checks),
        "source_sha256": source_hashes,
    }
    for name in ("azure-identity", "azure-storage-blob", "azure-core"):
        try:
            report["optional_dependencies"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report["optional_dependencies"][name] = None
    (destination / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {destination / 'summary.json'}")
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
