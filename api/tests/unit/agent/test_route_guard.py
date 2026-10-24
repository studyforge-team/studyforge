"""Pure tests for the routing guards (WP6 derivations, WP7 engineering signal)."""

import pytest

from app.agent.route_guard import has_eng_signal, is_derivation

DERIVATIONS = [
    (
        "Derive the design equation of an ideal CSTR from a steady-state mole balance on "
        "species A, and show how it gives the volume for first-order kinetics."
    ),
    "Derive the Gibbs-Duhem equation for a binary solution at constant T and P.",
    (
        "Derive the unsteady one-dimensional heat conduction equation in a slab by "
        "performing an energy balance on a thin shell of thickness dx."
    ),
    (
        "Derive the Rachford-Rice equation for an isothermal flash from the overall and "
        "component balances and the K-value definition."
    ),
    (
        "Derive the solution for unsteady diffusion into a semi-infinite medium with "
        "constant surface concentration, using a similarity (Boltzmann) variable."
    ),
    "Draw the shell balance element for heat conduction in a fin.",
    "Derive Fick's 2nd law for C_A0 and x1 in a 1D slab.",
]


@pytest.mark.parametrize("q", DERIVATIONS)
def test_derivations_detected(q: str) -> None:
    assert is_derivation(q)


@pytest.mark.parametrize(
    "q",
    [
        (
            "Derive the CSTR design equation, then find V for X = 0.8 with k = 0.3 1/min "
            "and v0 = 2 L/min"
        ),
        "Show that the pressure drop is 50 kPa at 20 C.",
        "Why does a fin lose heat?",
    ],
)
def test_not_derivations(q: str) -> None:
    assert not is_derivation(q)


def test_eng_signal() -> None:
    wilke = (
        "Estimate the diffusivity of dilute acetic acid in water at 25 C using the "
        "Wilke-Chang correlation."
    )
    assert has_eng_signal(wilke)
    assert has_eng_signal("Pressure is 200 kPa at 300 K")
    assert not has_eng_signal("Who won the IPL final last night?")
    assert not has_eng_signal("What is the stock price of Reliance now?")
