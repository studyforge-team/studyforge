"""Unit tests for T2: BlankItem schema and grading logic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.quiz import BlankItem, Quiz


class TestBlankItemSchema:
    def _valid_blank(self, **kwargs) -> dict:
        return {
            "type": "blank",
            "topic": "Thermodynamics",
            "stem": "The first law states that energy is ____.",
            "answers": ["conserved"],
            "explanation": "Energy cannot be created or destroyed.",
            **kwargs,
        }

    def test_valid_blank_item(self):
        item = BlankItem(**self._valid_blank())
        assert item.type == "blank"
        assert "____" in item.stem

    def test_stem_must_have_blank_placeholder(self):
        with pytest.raises(ValidationError, match="____"):
            BlankItem(**self._valid_blank(stem="No blank here."))

    def test_answers_min_one(self):
        with pytest.raises(ValidationError):
            BlankItem(**self._valid_blank(answers=[]))

    def test_answers_max_five(self):
        with pytest.raises(ValidationError):
            BlankItem(**self._valid_blank(answers=["a", "b", "c", "d", "e", "f"]))

    def test_answer_too_long(self):
        with pytest.raises(ValidationError, match="60"):
            BlankItem(**self._valid_blank(answers=["x" * 61]))

    def test_empty_answer_rejected(self):
        with pytest.raises(ValidationError):
            BlankItem(**self._valid_blank(answers=["  "]))

    def test_multiple_answers_accepted(self):
        item = BlankItem(**self._valid_blank(answers=["conserved", "preserved"]))
        assert len(item.answers) == 2


class TestBlankItemGrading:
    """The grading normalize logic (lowercase + trim + collapse spaces).

    This is replicated here to test the Python-side logic independently of
    the frontend.  The frontend normalizes the same way.
    """

    @staticmethod
    def normalize(s: str) -> str:
        import re
        return re.sub(r"\s+", " ", s.strip().lower())

    def grade(self, user_input: str, answers: list[str]) -> bool:
        norm_user = self.normalize(user_input)
        return norm_user in [self.normalize(a) for a in answers]

    def test_exact_match(self):
        assert self.grade("conserved", ["conserved"])

    def test_case_insensitive(self):
        assert self.grade("CONSERVED", ["conserved"])

    def test_extra_spaces(self):
        assert self.grade("  conserved  ", ["conserved"])

    def test_internal_spaces_collapsed(self):
        assert self.grade("heat   transfer", ["heat transfer"])

    def test_wrong_answer(self):
        assert not self.grade("entropy", ["energy"])

    def test_multiple_valid_answers(self):
        assert self.grade("preserved", ["conserved", "preserved"])


class TestBlankItemInQuiz:
    """Ensure BlankItem is accepted inside a Quiz with the discriminated union."""

    def test_quiz_with_blank_item(self):
        data = {
            "title": "Fill Quiz",
            "items": [
                {
                    "type": "blank",
                    "topic": "CRE",
                    "stem": "The CSTR residence time is ____.",
                    "answers": ["tau"],
                    "explanation": "tau = V/v_0",
                }
            ],
        }
        quiz = Quiz.model_validate(data)
        assert quiz.items[0].type == "blank"
