"""Build the Jev request body shared by preview and execution."""

from .cases import Variant


DEFAULT_MODEL = "jev-latest"


def build_request(variant: Variant, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    """Build a JSON-ready request from the question and its visible passages."""
    visible_passages = variant.visible_passages
    choice_criteria: dict[str, str] = {
        label: f"Passage {label}" for label in visible_passages
    }
    choice_criteria["none"] = "No passage fully answers the question"

    return {
        "model": model,
        "state": {
            "question": variant.question,
            "passages": visible_passages,
        },
        "questions": {
            "passage": {
                "type": "choice",
                "instructions": "Select the passage that fully answers the question by itself.",
                "criteria": choice_criteria,
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
