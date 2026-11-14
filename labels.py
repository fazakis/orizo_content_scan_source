"""Map detector labels to the categories the service returns."""
from __future__ import annotations

# Detector label -> (category, weight).
ACTIONABLE_LABELS: dict[str, tuple[str, float]] = {
    'FEMALE_GENITALIA_EXPOSED': ('explicit_nudity', 1.0),
    'MALE_GENITALIA_EXPOSED': ('explicit_nudity', 1.0),
    'ANUS_EXPOSED': ('explicit_nudity', 1.0),
    'FEMALE_BREAST_EXPOSED': ('explicit', 1.0),
    'BUTTOCKS_EXPOSED': ('explicit', 0.7),
}

# Labels that are ignored. Any label not in ACTIONABLE_LABELS is ignored too.
FITNESS_NORMAL_LABELS = frozenset({
    'MALE_BREAST_EXPOSED',
    'FEMALE_BREAST_COVERED',
    'BELLY_EXPOSED',
    'BELLY_COVERED',
    'ARMPITS_EXPOSED',
    'ARMPITS_COVERED',
    'FEET_EXPOSED',
    'FEET_COVERED',
    'BUTTOCKS_COVERED',
    'FEMALE_GENITALIA_COVERED',
    'FACE_FEMALE',
    'FACE_MALE',
})


def categories_from_detections(detections) -> dict[str, float]:
    """[{class, score}, ...] -> {category: highest weighted score}."""
    scores: dict[str, float] = {}
    for detection in detections or []:
        label = str((detection or {}).get('class') or (detection or {}).get('label') or '')
        mapped = ACTIONABLE_LABELS.get(label.upper())
        if not mapped:
            continue
        category, weight = mapped
        try:
            score = float((detection or {}).get('score', 0.0))
        except (TypeError, ValueError):
            continue
        if score <= 0:
            continue
        scores[category] = max(scores.get(category, 0.0), min(1.0, score * weight))
    return scores
