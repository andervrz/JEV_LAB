"""Define reviewed contract cases and construct paired evidence variants."""

from dataclasses import dataclass
from typing import Literal


PassageLabel = Literal["A", "B", "C"]
Choice = Literal["A", "B", "C", "none"]
Condition = Literal["with_evidence", "without_evidence"]

PASSAGE_LABELS: tuple[PassageLabel, ...] = ("A", "B", "C")


@dataclass(frozen=True)
class Passage:
    """Store an excerpt verbatim with its location in the source paragraph."""

    text: str
    document_title: str
    paragraph_index: int
    start_offset: int

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.document_title.strip():
            raise ValueError("A passage needs text and a source document title.")
        if self.paragraph_index < 0 or self.start_offset < 0:
            raise ValueError("Paragraph index and start offset must be non-negative.")


@dataclass(frozen=True)
class Case:
    """Store a question, its annotated evidence, and three reviewed distractors."""

    case_id: str
    question: str
    evidence: Passage
    distractors: tuple[Passage, Passage, Passage]

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("A case needs an ID and a question.")
        if len(self.distractors) != 3:
            raise ValueError("A case needs exactly three distractors.")

        texts = {passage.text.strip() for passage in (self.evidence, *self.distractors)}
        if len(texts) != 4:
            raise ValueError("The evidence and distractors must have distinct texts.")


@dataclass(frozen=True)
class Variant:
    """Store three ordered passages and the reference data for one condition."""

    case_id: str
    question: str
    condition: Condition
    passages: tuple[Passage, Passage, Passage]
    expected_choice: Choice

    @property
    def visible_passages(self) -> dict[PassageLabel, str]:
        """Return option labels and texts for the model's shared state."""
        return {
            label: passage.text
            for label, passage in zip(PASSAGE_LABELS, self.passages, strict=True)
        }


def build_pair(case: Case, *, case_index: int) -> tuple[Variant, Variant]:
    """Use the case's zero-based index in the full sample to rotate A, B, C."""
    if case_index < 0:
        raise ValueError("Case index must be non-negative.")

    evidence_index = case_index % len(PASSAGE_LABELS)
    first, second, replacement = case.distractors
    with_evidence = [first, second]
    with_evidence.insert(evidence_index, case.evidence)

    # Keep the replacement in the same slot to control for position effects.
    without_evidence = with_evidence.copy()
    without_evidence[evidence_index] = replacement

    return (
        Variant(
            case_id=case.case_id,
            question=case.question,
            condition="with_evidence",
            passages=(with_evidence[0], with_evidence[1], with_evidence[2]),
            expected_choice=PASSAGE_LABELS[evidence_index],
        ),
        Variant(
            case_id=case.case_id,
            question=case.question,
            condition="without_evidence",
            passages=(without_evidence[0], without_evidence[1], without_evidence[2]),
            expected_choice="none",
        ),
    )
