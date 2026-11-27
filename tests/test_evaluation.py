import json
from decimal import Decimal
from pathlib import Path

import pytest

from jev_lab.cases import Choice, Condition
from jev_lab.evaluation import Accuracy, evaluate_run


def _record(
    case_id: str,
    condition: Condition,
    choice: Choice | None = None,
    score: float | None = None,
    *,
    attempt: int = 1,
    status: str = "success",
) -> dict[str, object]:
    return {
        "run_id": "test-run",
        "simulated": True,
        "case_id": case_id,
        "condition": condition,
        "attempt": attempt,
        "status": status,
        "expected_choice": "B" if condition == "with_evidence" else "none",
        "choice": choice,
        "score": score,
    }


def _write_run(path: Path, *records: dict[str, object]) -> Path:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def test_evaluate_run_matches_the_acceptance_example(tmp_path):
    path = _write_run(
        tmp_path / "test-run.jsonl",
        _record("renewal", "with_evidence", "B", 1.8),
        _record("renewal", "without_evidence", "B", 0.7),
    )

    report = evaluate_run(path)

    assert report.run_id == "test-run"
    assert report.simulated is True
    assert report.selection == Accuracy(correct=1, valid=1)
    assert report.selection.rate == 1.0
    assert report.abstention == Accuracy(correct=0, valid=1)
    assert report.abstention.rate == 0.0
    assert report.total_attempts == 2
    assert report.attempt_failures == {}
    assert report.failed_variants == 0
    assert report.incomplete_case_ids == ()
    [pair] = report.pairs
    assert pair.case_id == "renewal"
    assert pair.score_delta == Decimal("1.1")


def test_evaluate_run_counts_the_highest_attempt_once_and_retains_recovered_failures(tmp_path):
    path = _write_run(
        tmp_path / "test-run.jsonl",
        _record("renewal", "with_evidence", "B", 1.8, attempt=3),
        _record("renewal", "with_evidence", status="timeout"),
        _record("renewal", "with_evidence", status="network_error", attempt=2),
        _record("renewal", "without_evidence", "none", 0.7),
    )

    report = evaluate_run(path)

    assert report.total_attempts == 4
    assert report.attempt_failures == {"timeout": 1, "network_error": 1}
    assert report.failed_variants == 0
    assert report.selection == Accuracy(correct=1, valid=1)
    assert report.abstention == Accuracy(correct=1, valid=1)
    [pair] = report.pairs
    assert pair.with_evidence is not None
    assert pair.with_evidence.attempt == 3
    assert pair.score_delta == Decimal("1.1")


def test_evaluate_run_preserves_negative_and_zero_score_changes(tmp_path):
    path = _write_run(
        tmp_path / "test-run.jsonl",
        _record("negative", "with_evidence", "C", 0.2),
        _record("negative", "without_evidence", "none", 0.3),
        _record("zero", "with_evidence", "B", 0.7),
        _record("zero", "without_evidence", "none", 0.7),
    )

    report = evaluate_run(path)

    assert report.selection == Accuracy(correct=1, valid=2)
    assert report.abstention == Accuracy(correct=2, valid=2)
    assert [pair.score_delta for pair in report.pairs] == [Decimal("-0.1"), Decimal("0")]
    assert report.incomplete_case_ids == ()


def test_evaluate_run_tracks_failed_and_missing_variants(tmp_path):
    path = _write_run(
        tmp_path / "test-run.jsonl",
        _record("missing-variant", "with_evidence", "B", 1.8),
        _record("failed-variant", "with_evidence", status="timeout"),
        _record("failed-variant", "without_evidence", "none", 0),
        _record("failed-variant", "with_evidence", status="http_error", attempt=2),
    )

    report = evaluate_run(path)

    assert report.selection == Accuracy(correct=1, valid=1)
    assert report.abstention == Accuracy(correct=1, valid=1)
    assert report.attempt_failures == {"timeout": 1, "http_error": 1}
    assert report.failed_variants == 1
    assert report.incomplete_case_ids == ("missing-variant", "failed-variant")
    missing, failed = report.pairs
    assert missing.without_evidence is None
    assert failed.with_evidence is not None
    assert failed.with_evidence.status == "http_error"
    assert missing.score_delta is None
    assert failed.score_delta is None


def test_evaluate_run_reports_an_undefined_rate_for_zero_valid_responses(tmp_path):
    path = _write_run(
        tmp_path / "test-run.jsonl",
        _record("renewal", "with_evidence", status="invalid_response"),
        _record("renewal", "without_evidence", "A", 0.7),
    )

    report = evaluate_run(path)

    assert report.selection == Accuracy(correct=0, valid=0)
    assert report.selection.rate is None
    assert report.abstention == Accuracy(correct=0, valid=1)
    assert report.abstention.rate == 0


def test_evaluate_run_identifies_a_malformed_record_by_line_number(tmp_path):
    path = _write_run(tmp_path / "test-run.jsonl", _record("renewal", "with_evidence", "B", 1.8))
    with path.open("a", encoding="utf-8") as output:
        output.write('{"case_id":\n')

    with pytest.raises(ValueError, match="Invalid run record on line 2"):
        evaluate_run(path)


def test_evaluate_run_rejects_duplicate_attempts(tmp_path):
    record = _record("renewal", "with_evidence", "B", 1.8)
    path = _write_run(tmp_path / "test-run.jsonl", record, record)

    with pytest.raises(ValueError, match="Duplicate attempt on line 2"):
        evaluate_run(path)
