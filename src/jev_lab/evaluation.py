"""Evaluate a saved experiment run without querying Jev."""

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from .cases import PASSAGE_LABELS, Choice, Condition


@dataclass(frozen=True)
class Accuracy:
    """Count correct answers among valid answers for one condition."""

    correct: int
    valid: int

    @property
    def rate(self) -> float | None:
        return self.correct / self.valid if self.valid else None


@dataclass(frozen=True)
class AttemptResult:
    """Retain the fields needed to inspect and score an attempt."""

    attempt: int
    status: str
    expected_choice: Choice
    choice: Choice | None
    score: Decimal | None


@dataclass(frozen=True)
class PairResult:
    """Compare the final attempts for the two variants of a case."""

    case_id: str
    with_evidence: AttemptResult | None
    without_evidence: AttemptResult | None

    @property
    def score_delta(self) -> Decimal | None:
        if self.with_evidence is None or self.without_evidence is None:
            return None
        with_score = self.with_evidence.score
        without_score = self.without_evidence.score
        if with_score is None or without_score is None:
            return None
        return with_score - without_score


@dataclass(frozen=True)
class RunEvaluation:
    """Expose aggregate metrics and case-level results for one JSONL file."""

    run_id: str | None
    simulated: bool | None
    selection: Accuracy
    abstention: Accuracy
    total_attempts: int
    attempt_failures: dict[str, int]
    failed_variants: int
    pairs: tuple[PairResult, ...]

    @property
    def incomplete_case_ids(self) -> tuple[str, ...]:
        return tuple(pair.case_id for pair in self.pairs if pair.score_delta is None)


def evaluate_run(path: str | Path) -> RunEvaluation:
    """Summarize a run using the highest attempt number for each variant."""
    metadata: tuple[str, bool] | None = None
    final_attempts: dict[str, dict[Condition, AttemptResult]] = {}
    seen_attempts: set[tuple[str, Condition, int]] = set()
    attempt_failures: Counter[str] = Counter()

    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line, parse_float=Decimal)
                run_id, simulated, case_id, condition, result = _parse_record(record)
            except (ValueError, KeyError) as error:
                raise ValueError(f"Invalid run record on line {line_number}: {error}") from None

            if metadata is None:
                metadata = (run_id, simulated)
            elif metadata != (run_id, simulated):
                raise ValueError(f"Inconsistent run metadata on line {line_number}.")

            attempt_key = (case_id, condition, result.attempt)
            if attempt_key in seen_attempts:
                raise ValueError(f"Duplicate attempt on line {line_number}.")
            seen_attempts.add(attempt_key)
            if result.status != "success":
                attempt_failures[result.status] += 1

            case_results = final_attempts.setdefault(case_id, {})
            previous = case_results.get(condition)
            if previous is None or result.attempt > previous.attempt:
                case_results[condition] = result

    pairs = tuple(
        PairResult(case_id, results.get("with_evidence"), results.get("without_evidence"))
        for case_id, results in final_attempts.items()
    )
    run_id, simulated = metadata if metadata is not None else (None, None)
    return RunEvaluation(
        run_id=run_id,
        simulated=simulated,
        selection=_accuracy(pair.with_evidence for pair in pairs),
        abstention=_accuracy(pair.without_evidence for pair in pairs),
        total_attempts=len(seen_attempts),
        attempt_failures=dict(attempt_failures),
        failed_variants=sum(
            result.status != "success"
            for results in final_attempts.values()
            for result in results.values()
        ),
        pairs=pairs,
    )


def _accuracy(results: Iterable[AttemptResult | None]) -> Accuracy:
    valid = [result for result in results if result is not None and result.status == "success"]
    return Accuracy(sum(result.choice == result.expected_choice for result in valid), len(valid))


def _parse_record(record: object) -> tuple[str, bool, str, Condition, AttemptResult]:
    if not isinstance(record, dict):
        raise ValueError("Expected a JSON object.")
    run_id, simulated, case_id = record["run_id"], record["simulated"], record["case_id"]
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("Expected a non-empty run ID.")
    if not isinstance(simulated, bool):
        raise ValueError("Expected a boolean simulation marker.")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("Expected a non-empty case ID.")

    condition = record["condition"]
    if condition not in ("with_evidence", "without_evidence"):
        raise ValueError("Unknown variant condition.")
    attempt = record["attempt"]
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Expected a positive attempt number.")
    expected = record["expected_choice"]
    allowed_expected = PASSAGE_LABELS if condition == "with_evidence" else ("none",)
    if expected not in allowed_expected:
        raise ValueError("Invalid expected choice for the variant condition.")
    status = record["status"]
    if not isinstance(status, str) or not status.strip():
        raise ValueError("Expected a non-empty attempt status.")

    expected_choice = cast(Choice, expected)
    if status == "success":
        choice, value = record["choice"], record["score"]
        if choice not in (*PASSAGE_LABELS, "none"):
            raise ValueError("Invalid returned choice.")
        if type(value) not in (int, Decimal) or not 0 <= value <= 2:
            raise ValueError("Expected a numeric score between 0 and 2.")
        result = AttemptResult(
            attempt, status, expected_choice, cast(Choice, choice), Decimal(value)
        )
    else:
        result = AttemptResult(attempt, status, expected_choice, None, None)

    return run_id, simulated, case_id, cast(Condition, condition), result
