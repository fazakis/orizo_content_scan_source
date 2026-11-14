"""Prompts for the optional second stage."""
from __future__ import annotations

SAFE_PROMPTS: tuple[str, ...] = (
    'a shirtless man lifting weights in a gym',
    'a muscular man flexing to show his physique',
    'a woman in a sports bra exercising in a gym',
    'a woman in athletic leggings working out',
    'a bodybuilder posing on stage in competition trunks',
    'a person in running shorts and a vest running outdoors',
    'a person in compression shorts doing squats',
    'a fitness progress photo of a person in underwear showing their body',
    'a person in swimwear at a swimming pool',
    'a close-up of a person flexing an arm muscle',
    'a person stretching on a yoga mat',
    'a photograph of gym equipment',
    'an ordinary photograph of a clothed person',
)

UNSAFE_PROMPTS: tuple[str, ...] = (
    'explicit sexual activity between people',
    'full frontal nudity with exposed genitals',
    'a close-up photograph of exposed genitals',
    'pornographic content',
)

ALL_PROMPTS: tuple[str, ...] = SAFE_PROMPTS + UNSAFE_PROMPTS


def unsafe_confidence(probabilities) -> float:
    """Share of probability on the unsafe prompts. `probabilities` must align with ALL_PROMPTS."""
    values = list(probabilities or [])
    if len(values) != len(ALL_PROMPTS):
        return -1.0
    unsafe = values[len(SAFE_PROMPTS):]
    total = sum(float(v) for v in values) or 1.0
    return max(0.0, min(1.0, sum(float(v) for v in unsafe) / total))


def merge_second_opinion(first: float, refined: float, *, raise_cap: float) -> float:
    """Combine the first-pass and second-stage scores."""
    if refined > first:
        return min(refined, raise_cap)
    return refined
