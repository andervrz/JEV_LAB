"""Preview, run, and report on Jev lab experiments from the terminal."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from dotenv import dotenv_values
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .cases import Case, Passage, build_pair
from .client import DEFAULT_TIMEOUT, query_jev
from .evaluation import Accuracy, AttemptResult, evaluate_run
from .experiment import run_experiment
from .questions import DEFAULT_MODEL, build_request


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line options and invoke the selected command."""
    args = _build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-lab", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    inputs = argparse.ArgumentParser(add_help=False)
    inputs.add_argument(
        "--cases", type=Path, default=Path("data/cases.json"), help="Case file (data/cases.json)."
    )
    inputs.add_argument("--model", default=DEFAULT_MODEL, help=f"Jev model ({DEFAULT_MODEL}).")

    preview = commands.add_parser("preview", parents=[inputs], help="Print one Jev request body.")
    preview.add_argument("--case", dest="case_id", help="Case ID (defaults to the first case).")
    preview.add_argument(
        "--condition",
        choices=("with_evidence", "without_evidence"),
        default="with_evidence",
        help="Variant to preview (with_evidence).",
    )
    preview.set_defaults(handler=_preview)

    run = commands.add_parser("run", parents=[inputs], help="Query Jev and save a JSONL run.")
    selection = run.add_mutually_exclusive_group()
    selection.add_argument("--case", dest="case_id", help="Run a specific case by ID.")
    selection.add_argument(
        "--count", type=int, choices=(1, 10), default=1, help="Run the first one or ten cases (1)."
    )
    run.add_argument("--results-dir", type=Path, default=Path("results"), help="Output directory.")
    run.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout in seconds.")
    run.add_argument("--max-attempts", type=int, default=1, help="Attempt limit per variant (1).")
    run.set_defaults(handler=_run)

    report = commands.add_parser("report", help="Summarize a saved run.")
    report.add_argument("path", type=Path, help="Path to the run's JSONL file.")
    report.set_defaults(handler=_report)
    return parser


def _preview(args: argparse.Namespace) -> int:
    if not args.model.strip():
        raise ValueError("The request needs a model name.")
    (case_index, case), = _select_cases(args.cases, args.case_id, count=1)
    with_evidence, without_evidence = build_pair(case, case_index=case_index)
    variant = with_evidence if args.condition == "with_evidence" else without_evidence
    body = build_request(variant, model=args.model)
    print(json.dumps(body, ensure_ascii=False, allow_nan=False))
    return 0


def _run(args: argparse.Namespace) -> int:
    selected_cases = _select_cases(args.cases, args.case_id, count=args.count)
    if not 0 < args.timeout < float("inf"):
        raise ValueError("The timeout must be positive and finite.")
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if api_key is None:
        api_key = dotenv_values(".env", interpolate=False).get("TYPESAFE_API_KEY")
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("Set TYPESAFE_API_KEY in the environment or in .env to run Jev.")
    if any(character.isspace() for character in api_key):
        raise ValueError("TYPESAFE_API_KEY must not contain whitespace.")

    path = run_experiment(
        selected_cases,
        partial(query_jev, api_key=api_key, timeout=args.timeout),
        simulated=False,
        results_dir=args.results_dir,
        model=args.model,
        max_attempts=args.max_attempts,
    )
    print(path)
    failures = evaluate_run(path).failed_variants
    if failures:
        print(f"{failures} variant(s) failed. Inspect the saved run with report.", file=sys.stderr)
        return 1
    return 0


def _select_cases(path: Path, case_id: str | None, *, count: int) -> list[tuple[int, Case]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"{path} must contain a cases array.")

    indexed_cases = []
    known_ids: set[str] = set()
    for index, record in enumerate(data["cases"]):
        try:
            first, second, third = record["distractors"]
            case = Case(
                case_id=record["case_id"],
                question=record["question"],
                evidence=Passage(**record["evidence"]),
                distractors=(Passage(**first), Passage(**second), Passage(**third)),
            )
            if case.case_id in known_ids:
                raise ValueError(f"Duplicate case ID {case.case_id!r}.")
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path}, case {index + 1}: {error}") from None
        indexed_cases.append((index, case))
        known_ids.add(case.case_id)

    if case_id is not None:
        for item in indexed_cases:
            if item[1].case_id == case_id:
                return [item]
        raise ValueError(f"Case {case_id!r} is not in {path}.")
    if len(indexed_cases) < count:
        raise ValueError(f"Requested {count} case(s), but {path} contains {len(indexed_cases)}.")
    return indexed_cases[:count]


def _report(args: argparse.Namespace) -> int:
    report = evaluate_run(args.path)
    console = Console()
    run_kind = {True: "simulated", False: "live", None: "empty"}[report.simulated]
    console.print(Text(f"Run {report.run_id or args.path.stem} ({run_kind})"))

    summary = Table()
    summary.add_column("Metric")
    summary.add_column("Result")
    summary.add_row("Selection", _format_accuracy(report.selection))
    summary.add_row("Abstention", _format_accuracy(report.abstention))
    summary.add_row("Attempts", str(report.total_attempts))
    failed_attempts = sum(report.attempt_failures.values())
    failures = ", ".join(f"{kind}: {count}" for kind, count in report.attempt_failures.items())
    summary.add_row("Failed attempts", Text(f"{failed_attempts} ({failures})" if failures else "0"))
    summary.add_row("Failed variants", str(report.failed_variants))
    summary.add_row("Incomplete pairs", str(len(report.incomplete_case_ids)))
    console.print(summary)

    if report.pairs:
        pairs = Table(caption="Choice / expected choice · score")
        pairs.add_column("Case", overflow="fold")
        pairs.add_column("With evidence")
        pairs.add_column("Without evidence")
        pairs.add_column("Score change", justify="right")
        for pair in report.pairs:
            delta = pair.score_delta
            pairs.add_row(
                Text(pair.case_id),
                Text(_format_variant(pair.with_evidence)),
                Text(_format_variant(pair.without_evidence)),
                f"{delta:+f}" if delta is not None else "—",
            )
        console.print(pairs)
    return 0


def _format_accuracy(accuracy: Accuracy) -> str:
    rate = accuracy.rate
    percentage = f"{rate:.1%}" if rate is not None else "n/a"
    return f"{accuracy.correct}/{accuracy.valid} ({percentage})"


def _format_variant(attempt: AttemptResult | None) -> str:
    if attempt is None:
        return "Missing"
    if attempt.status != "success":
        return f"{attempt.status} (attempt {attempt.attempt})"
    return f"{attempt.choice} / {attempt.expected_choice} · {attempt.score}"


if __name__ == "__main__":
    raise SystemExit(main())
