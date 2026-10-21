import pytest

from app.agent.loop import _LIVE

GIVEN_PRICE_CALCS = [
    "If the price of diesel is ₹90/L and a pump uses 12 L/h, what is the fuel cost for 8 hours?",
    "The price of gold is $60 per gram; what is the cost of 2.5 g?",
    "The price of petrol is 105 Rs per litre. What is the cost of 40 L?",
    "The price of bitcoin is 30000 USD; convert 0.5 BTC to USD.",
    "The current price of diesel is ₹90/L; what does 50 L cost?",
    "Current price of gold is $60/g, find the cost of 3 g.",
]

LIVE_QUESTIONS = [
    "what is the price of petrol today",
    "current price of gold",
    "latest price of bitcoin",
    "price of diesel now",
    "who won the IPL final yesterday",
    "stock price of Tesla",
]

STUDY_QUESTIONS = [
    "price elasticity of demand",
    "current density in the wire",
]


@pytest.mark.parametrize("q", GIVEN_PRICE_CALCS)
def test_given_price_calculation_is_not_live(q: str) -> None:
    assert _LIVE.search(q) is None


@pytest.mark.parametrize("q", LIVE_QUESTIONS)
def test_live_question_is_refused(q: str) -> None:
    assert _LIVE.search(q) is not None


@pytest.mark.parametrize("q", STUDY_QUESTIONS)
def test_study_phrases_pass(q: str) -> None:
    assert _LIVE.search(q) is None
