import json

import pytest

from jev_lab.cases import Case, Passage, build_pair
from jev_lab.questions import build_request


@pytest.fixture
def renewal_case() -> Case:
    return Case(
        case_id="example-renewal",
        question="How much advance notice is required to prevent renewal?",
        evidence=Passage("Non-renewal requires 60 days' written notice.", "Example contract", 0, 0),
        distractors=(
            Passage("Invoices are payable within 15 days.", "Example contract", 1, 0),
            Passage("A breach must be cured within 30 days.", "Example contract", 2, 0),
            Passage("The parties may amend the contract in writing.", "Example contract", 3, 0),
        ),
    )


def test_build_request_produces_the_jev_json_contract(renewal_case: Case):
    with_evidence, _ = build_pair(renewal_case, case_index=1)

    assert json.loads(json.dumps(build_request(with_evidence))) == {
        "model": "jev-latest",
        "state": {
            "question": "How much advance notice is required to prevent renewal?",
            "passages": {
                "A": "Invoices are payable within 15 days.",
                "B": "Non-renewal requires 60 days' written notice.",
                "C": "A breach must be cured within 30 days.",
            },
        },
        "questions": {
            "passage": {
                "type": "choice",
                "instructions": "Select the passage that fully answers the question by itself.",
                "criteria": {
                    "A": "Passage A",
                    "B": "Passage B",
                    "C": "Passage C",
                    "none": "No passage fully answers the question",
                },
            },
            "sufficiency": {
                "type": "score",
                "instructions": "Rate the evidence across all passages for answering the question.",
                "criteria": [
                    "No relevant evidence",
                    "Relevant but incomplete evidence",
                    "The passages together explicitly support a complete answer to the question",
                ],
            },
        },
    }


def test_build_request_keeps_both_variants_on_the_same_rubric(renewal_case: Case):
    with_evidence, without_evidence = build_pair(renewal_case, case_index=1)
    with_request = json.loads(json.dumps(build_request(with_evidence, model="test-model")))
    without_request = json.loads(json.dumps(build_request(without_evidence, model="test-model")))

    assert with_request["model"] == without_request["model"] == "test-model"
    assert with_request["questions"] == without_request["questions"]
    assert without_request["state"]["question"] == with_request["state"]["question"]
    assert without_request["state"]["passages"] == {
        "A": "Invoices are payable within 15 days.",
        "B": "The parties may amend the contract in writing.",
        "C": "A breach must be cured within 30 days.",
    }
