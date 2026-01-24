"""
Diversity service for selecting diverse parcel proposals.

Implements the algorithm from PLAN_V2 Part D:
- Selects 3 different proposals with explanations
- Ensures variety in location and/or profile
- Adds "surprise" factor for unexpected value
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum


class ParcelProfile(str, Enum):
    """Dominant characteristic of a parcel."""
    QUIET = "quiet"       # High quietness score
    GREEN = "green"       # High nature score
    ACCESSIBLE = "accessible"  # High accessibility score
    SPACIOUS = "spacious"  # Large area


@dataclass
class DiverseProposal:
    """A parcel proposal with explanation."""
    parcel: Dict[str, Any]
    label: str  # e.g., "Najlepsze dopasowanie", "Inna okolica"
    reason: str  # Why this parcel was selected


@dataclass
class UserFeedback:
    """Parsed user feedback about search results."""
    preferred_index: Optional[int] = None
    liked_features: List[str] = field(default_factory=list)
    disliked_features: List[str] = field(default_factory=list)
    new_requirements: List[str] = field(default_factory=list)


def get_profile(parcel: Dict[str, Any]) -> ParcelProfile:
    """
    Determine the dominant characteristic of a parcel.

    Returns the profile with the highest relative score.
    """
    scores = {
        ParcelProfile.QUIET: parcel.get("quietness_score", 0) or 0,
        ParcelProfile.GREEN: parcel.get("nature_score", 0) or 0,
        ParcelProfile.ACCESSIBLE: parcel.get("accessibility_score", 0) or 0,
        ParcelProfile.SPACIOUS: min(100, (parcel.get("area_m2", 0) or 0) / 20),  # 2000m² = 100
    }
    return max(scores, key=scores.get)


def explain_match(parcel: Dict[str, Any], priorities: List[str]) -> str:
    """Generate explanation for why this parcel matches user priorities."""
    explanations = []

    # Quietness
    quietness = parcel.get("quietness_score", 0) or 0
    if "quiet" in priorities or "cicha" in priorities:
        if quietness >= 85:
            explanations.append(f"bardzo cicha okolica ({int(quietness)}/100)")
        elif quietness >= 70:
            explanations.append(f"cicha okolica ({int(quietness)}/100)")

    # Nature
    nature = parcel.get("nature_score", 0) or 0
    dist_forest = parcel.get("dist_to_forest")
    if "nature" in priorities or "las" in priorities or "zielona" in priorities:
        if dist_forest and dist_forest < 200:
            explanations.append(f"las w {int(dist_forest)}m")
        elif nature >= 70:
            explanations.append(f"zielona okolica ({int(nature)}/100)")

    # Accessibility
    accessibility = parcel.get("accessibility_score", 0) or 0
    if "accessible" in priorities or "dojazd" in priorities:
        if accessibility >= 70:
            explanations.append(f"dobry dojazd ({int(accessibility)}/100)")

    # Area
    area = parcel.get("area_m2", 0) or 0
    if "duza" in priorities or "spacious" in priorities:
        if area >= 1500:
            explanations.append(f"duża działka ({int(area)}m²)")

    # Default
    if not explanations:
        explanations.append("dopasowanie do kryteriów")

    return ", ".join(explanations)


def explain_difference(parcel: Dict[str, Any], reference: Dict[str, Any]) -> str:
    """Explain how this parcel differs from the reference."""
    differences = []

    # Location difference
    if parcel.get("dzielnica") != reference.get("dzielnica"):
        differences.append(f"inna dzielnica: {parcel.get('dzielnica', 'nieznana')}")
    elif parcel.get("miejscowosc") != reference.get("miejscowosc"):
        differences.append(f"inna miejscowość: {parcel.get('miejscowosc', 'nieznana')}")

    # Profile differences
    ref_profile = get_profile(reference)
    new_profile = get_profile(parcel)

    if new_profile != ref_profile:
        profile_names = {
            ParcelProfile.QUIET: "cichsza",
            ParcelProfile.GREEN: "bardziej zielona",
            ParcelProfile.ACCESSIBLE: "lepszy dojazd",
            ParcelProfile.SPACIOUS: "większa",
        }
        differences.append(profile_names.get(new_profile, "inny charakter"))

    # Size difference
    area_diff = (parcel.get("area_m2", 0) or 0) - (reference.get("area_m2", 0) or 0)
    if abs(area_diff) >= 200:
        if area_diff > 0:
            differences.append(f"+{int(area_diff)}m² większa")
        else:
            differences.append(f"{int(area_diff)}m² mniejsza")

    # Price difference (if available)
    # Note: prices are estimated, not actual

    return ", ".join(differences) if differences else "alternatywna opcja"


def find_surprise_factor(parcel: Dict[str, Any], priorities: List[str]) -> Optional[str]:
    """Find something positive about the parcel that the user didn't ask for."""
    surprises = []

    # Quietness surprise
    if "quiet" not in priorities and "cicha" not in priorities:
        quietness = parcel.get("quietness_score", 0) or 0
        if quietness >= 85:
            surprises.append("wyjątkowo cicha okolica")

    # Nature surprise
    if "nature" not in priorities and "las" not in priorities:
        dist_forest = parcel.get("dist_to_forest")
        if dist_forest and dist_forest < 200:
            surprises.append("las tuż obok")

    # Building height surprise
    max_height = parcel.get("pog_maks_wysokosc_m")
    if max_height and max_height > 12:
        floors = int(max_height / 3)
        surprises.append(f"można wybudować {floors} piętra")

    # School proximity
    if "szkola" not in priorities and "school" not in priorities:
        dist_school = parcel.get("dist_to_school")
        if dist_school and dist_school < 500:
            surprises.append(f"szkoła w {int(dist_school)}m")

    # Under construction (development area)
    if parcel.get("under_construction"):
        surprises.append("okolica się rozwija")

    # Water proximity
    if "woda" not in priorities and "water" not in priorities:
        dist_water = parcel.get("dist_to_water")
        if dist_water and dist_water < 300:
            surprises.append(f"woda w {int(dist_water)}m")

    return surprises[0] if surprises else None


def select_diverse_proposals(
    candidates: List[Dict[str, Any]],
    user_priorities: List[str],
    count: int = 3
) -> List[DiverseProposal]:
    """
    Select diverse proposals from search results.

    Strategy:
    1. Best match - highest score for user priorities
    2. Alternative - different location OR different profile
    3. Surprise - something the user didn't ask for but might appreciate

    Args:
        candidates: List of parcel dictionaries from search results
        user_priorities: List of priority keywords (e.g., ["quiet", "nature"])
        count: Number of proposals to return (default 3)

    Returns:
        List of DiverseProposal objects with labels and explanations
    """
    if not candidates:
        return []

    proposals: List[DiverseProposal] = []
    used_districts: Set[str] = set()
    used_profiles: Set[ParcelProfile] = set()
    used_ids: Set[str] = set()

    # 1. Best match (first candidate, assuming pre-sorted by relevance)
    best = candidates[0]
    proposals.append(DiverseProposal(
        parcel=best,
        label="Najlepsze dopasowanie",
        reason=explain_match(best, user_priorities)
    ))
    used_districts.add(best.get("dzielnica", ""))
    used_profiles.add(get_profile(best))
    used_ids.add(best.get("id", ""))

    if len(candidates) == 1:
        return proposals

    # 2. Alternative (different location or profile)
    for c in candidates[1:]:
        if c.get("id", "") in used_ids:
            continue

        district = c.get("dzielnica", "")
        profile = get_profile(c)

        # Prefer different district, otherwise different profile
        if district not in used_districts or profile not in used_profiles:
            label = "Inna okolica" if district not in used_districts else "Inny charakter"
            proposals.append(DiverseProposal(
                parcel=c,
                label=label,
                reason=explain_difference(c, best)
            ))
            used_districts.add(district)
            used_profiles.add(profile)
            used_ids.add(c.get("id", ""))
            break

    if len(proposals) >= count or len(candidates) <= 2:
        return proposals[:count]

    # 3. Surprise - find something unexpected
    for c in candidates:
        if c.get("id", "") in used_ids:
            continue

        surprise = find_surprise_factor(c, user_priorities)
        if surprise:
            proposals.append(DiverseProposal(
                parcel=c,
                label="Może Cię zainteresuje",
                reason=surprise
            ))
            used_ids.add(c.get("id", ""))
            break

    # If still need more, add next best candidates
    if len(proposals) < count:
        for c in candidates:
            if c.get("id", "") not in used_ids:
                proposals.append(DiverseProposal(
                    parcel=c,
                    label="Dodatkowa opcja",
                    reason=explain_match(c, user_priorities)
                ))
                used_ids.add(c.get("id", ""))
                if len(proposals) >= count:
                    break

    return proposals[:count]


def parse_user_feedback(message: str, proposals: List[DiverseProposal]) -> UserFeedback:
    """
    Parse natural language feedback from user about proposals.

    Args:
        message: User's message
        proposals: Current proposals shown to user

    Returns:
        UserFeedback with parsed preferences
    """
    feedback = UserFeedback()
    msg = message.lower()

    # Detect selection
    selection_keywords = [
        (["pierwsz", "1.", "ta pierwsza", "numer 1", "opcja 1"], 0),
        (["drug", "2.", "ta druga", "numer 2", "opcja 2"], 1),
        (["trzeci", "3.", "ta trzecia", "numer 3", "opcja 3"], 2),
    ]

    for keywords, index in selection_keywords:
        if any(kw in msg for kw in keywords):
            feedback.preferred_index = index
            break

    # Detect liked features
    liked_keywords = {
        "las": "nature",
        "cisz": "quiet",
        "spok": "quiet",
        "ziel": "nature",
        "szkoł": "schools",
        "sklep": "shops",
        "przystane": "transport",
        "dojazd": "accessibility",
        "duż": "size",
    }
    for kw, feature in liked_keywords.items():
        if kw in msg and feature not in feedback.liked_features:
            feedback.liked_features.append(feature)

    # Detect disliked features / problems
    if "za mał" in msg or "mniejsza" in msg:
        feedback.new_requirements.append("larger")
    if "za duż" in msg:
        feedback.new_requirements.append("smaller")
    if "za daleko" in msg:
        feedback.disliked_features.append("distance")
    if "za drogie" in msg or "budżet" in msg or "tańsze" in msg:
        feedback.new_requirements.append("cheaper")
    if "za głośn" in msg or "hałas" in msg:
        feedback.new_requirements.append("quieter")

    return feedback


def format_proposal_for_display(
    proposal: DiverseProposal,
    index: int,
    include_estimate: bool = True
) -> str:
    """
    Format a proposal for display to user.

    Args:
        proposal: The proposal to format
        index: 1-based index for display
        include_estimate: Whether to include price estimate

    Returns:
        Formatted string for display
    """
    p = proposal.parcel

    # Location
    location = p.get("dzielnica") or p.get("miejscowosc") or p.get("gmina", "Nieznana")

    # Basic info
    area = p.get("area_m2", 0)
    quietness = p.get("quietness_score", 0)
    nature = p.get("nature_score", 0)

    # Distances
    dist_forest = p.get("dist_to_forest")
    dist_school = p.get("dist_to_school")

    lines = [
        f"**{index}. {location}** ({proposal.label})",
    ]

    # Key metrics line
    metrics = []
    if area:
        metrics.append(f"📐 {int(area):,} m²".replace(",", " "))
    if dist_forest:
        metrics.append(f"🌲 Las: {int(dist_forest)}m")
    if quietness:
        metrics.append(f"🔇 Cisza: {int(quietness)}/100")
    if dist_school and dist_school < 1000:
        metrics.append(f"🏫 Szkoła: {int(dist_school)}m")

    if metrics:
        lines.append(" | ".join(metrics))

    # Reason
    lines.append(f"→ {proposal.reason}")

    return "\n".join(lines)
