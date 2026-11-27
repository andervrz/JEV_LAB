import json
from dataclasses import replace
from pathlib import Path

import pytest

from jev_lab.cases import Case, Passage, build_pair


@pytest.fixture
def renewal_case() -> Case:
    cases_path = Path(__file__).resolve().parents[1] / "data" / "cases.json"
    dataset = json.loads(cases_path.read_text(encoding="utf-8"))
    reviewed_case = dataset["cases"][0]
    first, second, third = reviewed_case["distractors"]
    return Case(
        case_id=reviewed_case["case_id"],
        question=reviewed_case["question"],
        evidence=Passage(**reviewed_case["evidence"]),
        distractors=(Passage(**first), Passage(**second), Passage(**third)),
    )


@pytest.mark.parametrize(("case_index", "evidence_label"), [(0, "A"), (1, "B"), (2, "C"), (3, "A")])
def test_build_pair_replaces_only_the_evidence(renewal_case, case_index, evidence_label):
    with_evidence, without_evidence = build_pair(renewal_case, case_index=case_index)

    assert with_evidence.condition == "with_evidence"
    assert without_evidence.condition == "without_evidence"
    assert with_evidence.case_id == without_evidence.case_id == renewal_case.case_id
    assert with_evidence.question == without_evidence.question == renewal_case.question
    assert with_evidence.expected_choice == evidence_label
    assert without_evidence.expected_choice == "none"

    with_texts = with_evidence.visible_passages
    without_texts = without_evidence.visible_passages
    assert list(with_texts) == list(without_texts) == ["A", "B", "C"]
    assert with_texts[evidence_label] == renewal_case.evidence.text
    assert without_texts[evidence_label] == renewal_case.distractors[2].text

    shared_labels = [label for label in with_texts if label != evidence_label]
    assert [with_texts[label] for label in shared_labels] == [
        distractor.text for distractor in renewal_case.distractors[:2]
    ]
    assert [with_texts[label] for label in shared_labels] == [
        without_texts[label] for label in shared_labels
    ]


def test_case_rejects_missing_distractor(renewal_case):
    with pytest.raises(ValueError, match="exactly three distractors"):
        replace(renewal_case, distractors=renewal_case.distractors[:2])


def test_case_rejects_duplicate_visible_text(renewal_case):
    first, second, third = renewal_case.distractors
    duplicate = replace(third, text=f" {renewal_case.evidence.text} ")

    with pytest.raises(ValueError, match="distinct texts"):
        replace(renewal_case, distractors=(first, second, duplicate))


def test_build_pair_rejects_negative_case_index(renewal_case):
    with pytest.raises(ValueError, match="non-negative"):
        build_pair(renewal_case, case_index=-1)
