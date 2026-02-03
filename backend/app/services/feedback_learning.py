"""
Feedback Learning Service - Learning from user preferences.

Implements simple re-ranking based on user feedback:
- Favorites boost similar parcels
- Rejections penalize similar parcels
- Patterns extracted over time

This is the first step towards more sophisticated ML-based recommendations.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from loguru import logger

from app.memory import AgentState, WorkspaceManager, get_workspace_manager


@dataclass
class FeedbackEntry:
    """Single feedback entry."""
    parcel_id: str
    action: str  # "favorite", "reject", "view", "compare"
    timestamp: datetime
    session_id: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParcelFeatures:
    """Extracted features from a parcel for similarity."""
    district: Optional[str] = None
    size_category: Optional[str] = None
    quietness_category: Optional[str] = None
    nature_category: Optional[str] = None
    ownership_type: Optional[str] = None
    has_pog: bool = False
    pog_residential: bool = False
    dist_to_water_category: Optional[str] = None


class FeedbackLearningService:
    """Service for learning from user feedback.

    Implements:
    1. Simple re-ranking based on favorites/rejections
    2. Feature preference extraction
    3. Pattern persistence to workspace
    """

    def __init__(self, workspace_manager: Optional[WorkspaceManager] = None):
        """Initialize service."""
        self.workspace_manager = workspace_manager or get_workspace_manager()

    def extract_features(self, parcel: Dict[str, Any]) -> ParcelFeatures:
        """Extract features from parcel for similarity calculation."""
        return ParcelFeatures(
            district=parcel.get("dzielnica") or parcel.get("district"),
            size_category=parcel.get("size_category"),
            quietness_category=parcel.get("kategoria_ciszy"),
            nature_category=parcel.get("kategoria_natury"),
            ownership_type=parcel.get("typ_wlasnosci") or parcel.get("ownership_type"),
            has_pog=bool(parcel.get("has_pog")),
            pog_residential=bool(parcel.get("is_residential_zone")),
            dist_to_water_category=self._categorize_water_distance(
                parcel.get("dist_to_water")
            ),
        )

    def _categorize_water_distance(self, distance: Optional[float]) -> Optional[str]:
        """Categorize water distance."""
        if distance is None:
            return None
        if distance < 200:
            return "very_close"
        elif distance < 500:
            return "close"
        elif distance < 1000:
            return "moderate"
        else:
            return "far"

    def calculate_similarity(
        self,
        features1: ParcelFeatures,
        features2: ParcelFeatures,
    ) -> float:
        """Calculate similarity between two parcels (0-1)."""
        score = 0.0
        max_score = 0.0

        # District match (high weight)
        if features1.district and features2.district:
            max_score += 3.0
            if features1.district == features2.district:
                score += 3.0

        # Size category match
        if features1.size_category and features2.size_category:
            max_score += 2.0
            if features1.size_category == features2.size_category:
                score += 2.0

        # Quietness match
        if features1.quietness_category and features2.quietness_category:
            max_score += 2.0
            if features1.quietness_category == features2.quietness_category:
                score += 2.0

        # Nature match
        if features1.nature_category and features2.nature_category:
            max_score += 2.0
            if features1.nature_category == features2.nature_category:
                score += 2.0

        # Ownership match
        if features1.ownership_type and features2.ownership_type:
            max_score += 1.0
            if features1.ownership_type == features2.ownership_type:
                score += 1.0

        # POG match
        max_score += 1.0
        if features1.has_pog == features2.has_pog:
            score += 0.5
        if features1.pog_residential == features2.pog_residential:
            score += 0.5

        # Water distance match
        if features1.dist_to_water_category and features2.dist_to_water_category:
            max_score += 1.0
            if features1.dist_to_water_category == features2.dist_to_water_category:
                score += 1.0

        return score / max_score if max_score > 0 else 0.5

    def rerank_results(
        self,
        results: List[Dict[str, Any]],
        state: AgentState,
        boost_factor: float = 1.5,
        penalty_factor: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Re-rank search results based on user feedback.

        Args:
            results: Original search results
            state: Agent state with favorites/rejections
            boost_factor: Score multiplier for similar-to-favorites
            penalty_factor: Score multiplier for similar-to-rejections

        Returns:
            Re-ranked results
        """
        favorites = state.working.search_state.favorited_parcels
        rejections = state.working.search_state.rejected_parcels

        if not favorites and not rejections:
            return results  # No feedback to learn from

        # Extract features from favorites and rejections
        favorite_features = []
        rejection_features = []

        # Get favorite parcel features from results or history
        for result in results:
            parcel_id = result.get("id_dzialki")
            if parcel_id in favorites:
                favorite_features.append(self.extract_features(result))
            elif parcel_id in rejections:
                rejection_features.append(self.extract_features(result))

        # Calculate adjusted scores for each result
        scored_results = []
        for result in results:
            parcel_id = result.get("id_dzialki")

            # Skip already favorited/rejected
            if parcel_id in favorites or parcel_id in rejections:
                continue

            features = self.extract_features(result)
            base_score = result.get("score", 1.0)

            # Calculate similarity to favorites (boost)
            if favorite_features:
                avg_fav_similarity = sum(
                    self.calculate_similarity(features, fav)
                    for fav in favorite_features
                ) / len(favorite_features)
                base_score *= (1 + (boost_factor - 1) * avg_fav_similarity)

            # Calculate similarity to rejections (penalty)
            if rejection_features:
                avg_rej_similarity = sum(
                    self.calculate_similarity(features, rej)
                    for rej in rejection_features
                ) / len(rejection_features)
                base_score *= (1 - (1 - penalty_factor) * avg_rej_similarity)

            result["feedback_adjusted_score"] = base_score
            scored_results.append(result)

        # Sort by adjusted score
        scored_results.sort(
            key=lambda x: x.get("feedback_adjusted_score", 0),
            reverse=True
        )

        # Add back favorites at the top
        favorite_results = [r for r in results if r.get("id_dzialki") in favorites]
        return favorite_results + scored_results

    def extract_preference_patterns(
        self,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Extract preference patterns from feedback.

        Args:
            state: Agent state with favorites/rejections

        Returns:
            Extracted preference patterns
        """
        favorites = state.working.search_state.favorited_parcels
        rejections = state.working.search_state.rejected_parcels
        results = state.working.search_state.current_results

        if not favorites and not rejections:
            return {"patterns": [], "confidence": 0}

        # Build feature frequency from favorites
        feature_counts: Dict[str, Dict[str, int]] = {
            "district": {},
            "size_category": {},
            "quietness_category": {},
            "nature_category": {},
            "ownership_type": {},
            "pog_residential": {},
        }

        for result in results:
            if result.get("id_dzialki") not in favorites:
                continue

            features = self.extract_features(result)

            if features.district:
                feature_counts["district"][features.district] = \
                    feature_counts["district"].get(features.district, 0) + 1
            if features.size_category:
                feature_counts["size_category"][features.size_category] = \
                    feature_counts["size_category"].get(features.size_category, 0) + 1
            if features.quietness_category:
                feature_counts["quietness_category"][features.quietness_category] = \
                    feature_counts["quietness_category"].get(features.quietness_category, 0) + 1
            if features.nature_category:
                feature_counts["nature_category"][features.nature_category] = \
                    feature_counts["nature_category"].get(features.nature_category, 0) + 1

        # Extract patterns (features that appear in most favorites)
        patterns = []
        threshold = max(1, len(favorites) // 2)

        for feature_name, counts in feature_counts.items():
            for value, count in counts.items():
                if count >= threshold:
                    patterns.append({
                        "feature": feature_name,
                        "value": value,
                        "count": count,
                        "total_favorites": len(favorites),
                    })

        # Calculate confidence based on feedback volume
        confidence = min(len(favorites) / 5, 1.0)  # Max confidence at 5+ favorites

        return {
            "patterns": patterns,
            "confidence": confidence,
            "favorites_count": len(favorites),
            "rejections_count": len(rejections),
        }

    def save_feedback_to_workspace(
        self,
        state: AgentState,
    ) -> None:
        """Save feedback patterns to user workspace for persistence.

        Args:
            state: Agent state
        """
        user_id = state.user_id
        workspace = self.workspace_manager.get_user_workspace(user_id)

        # Extract patterns
        patterns = self.extract_preference_patterns(state)

        if patterns["patterns"]:
            # Save to workspace
            workspace.ensure_exists()

            # Update patterns file
            patterns_data = {
                "session_id": state.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "favorites": state.working.search_state.favorited_parcels,
                "rejections": state.working.search_state.rejected_parcels,
                "patterns": patterns["patterns"],
                "confidence": patterns["confidence"],
            }

            # Append to patterns history
            patterns_file = workspace.memory_dir / "feedback_patterns.jsonl"
            with open(patterns_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(patterns_data, ensure_ascii=False, default=str) + "\n")

            logger.info(f"Saved {len(patterns['patterns'])} feedback patterns for user {user_id}")

    def get_historical_preferences(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get historical preferences from workspace.

        Args:
            user_id: User ID

        Returns:
            Aggregated historical preferences
        """
        workspace = self.workspace_manager.get_user_workspace(user_id)
        patterns_file = workspace.memory_dir / "feedback_patterns.jsonl"

        if not patterns_file.exists():
            return {"patterns": [], "history_count": 0}

        # Load all patterns
        all_patterns = []
        with open(patterns_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    all_patterns.extend(data.get("patterns", []))

        # Aggregate patterns
        aggregated: Dict[str, Dict[str, int]] = {}
        for pattern in all_patterns:
            feature = pattern["feature"]
            value = pattern["value"]
            if feature not in aggregated:
                aggregated[feature] = {}
            aggregated[feature][value] = aggregated[feature].get(value, 0) + pattern["count"]

        return {
            "patterns": aggregated,
            "history_count": len(all_patterns),
        }


# Singleton
_feedback_service: Optional[FeedbackLearningService] = None


def get_feedback_learning_service() -> FeedbackLearningService:
    """Get the global feedback learning service instance."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackLearningService()
    return _feedback_service
