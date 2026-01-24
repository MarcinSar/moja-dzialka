"""
Evaluation Skill - Property comparison and selection.

This skill handles the EVALUATION phase of the funnel:
- Provides detailed parcel information
- Compares parcels
- Explains trade-offs
- Helps user make a decision
"""

from typing import List, Optional, Type, Dict, Any
from pydantic import BaseModel, Field

from ._base import ToolCallingSkill, SkillContext


class ParcelComparison(BaseModel):
    """Comparison between parcels."""
    parcel_a_id: str
    parcel_b_id: str
    winner_quietness: Optional[str] = None
    winner_nature: Optional[str] = None
    winner_accessibility: Optional[str] = None
    winner_price: Optional[str] = None
    summary: str = ""


class EvaluationOutput(BaseModel):
    """Structured output from evaluation skill."""

    # Internal reasoning
    thinking: str = Field(
        default="",
        description="Internal reasoning about evaluation"
    )

    # Response to user
    ai_response: str = Field(
        default="",
        description="Natural language evaluation/comparison"
    )

    # Parcel focus
    focused_parcel_id: Optional[str] = Field(
        default=None,
        description="Parcel being discussed in detail"
    )
    parcel_details_shown: bool = Field(
        default=False,
        description="Whether detailed info was shown"
    )

    # Comparison
    comparison_made: bool = Field(
        default=False,
        description="Whether parcels were compared"
    )
    comparisons: List[ParcelComparison] = Field(
        default_factory=list,
        description="Comparison results"
    )

    # User signals
    user_liked: List[str] = Field(
        default_factory=list,
        description="Parcel IDs user expressed interest in"
    )
    user_rejected: List[str] = Field(
        default_factory=list,
        description="Parcel IDs user rejected"
    )

    # Price estimation
    price_estimate_shown: bool = Field(
        default=False,
        description="Whether price estimate was provided"
    )
    estimated_value_range: Optional[str] = Field(
        default=None,
        description="Estimated value range (e.g., '600-750k zł')"
    )

    # Decision progress
    selection_made: bool = Field(
        default=False,
        description="Whether user selected a parcel"
    )
    selected_parcel_id: Optional[str] = Field(
        default=None,
        description="ID of selected parcel"
    )

    # Next steps
    suggested_action: Optional[str] = Field(
        default=None,
        description="Suggested next action"
    )


class EvaluationSkill(ToolCallingSkill):
    """Help user evaluate and compare properties."""

    @property
    def name(self) -> str:
        return "evaluation"

    @property
    def description(self) -> str:
        return "Help user evaluate and compare properties"

    @property
    def output_model(self) -> Type[BaseModel]:
        return EvaluationOutput

    @property
    def available_tools(self) -> List[str]:
        """Tools available during evaluation."""
        return [
            # Detail tools
            "get_parcel_details",
            "get_parcel_neighborhood",
            # Similar
            "find_similar_parcels",
            # Map
            "generate_map_data",
            # Price
            "get_district_prices",
            "estimate_parcel_value",
            # Can refine search if needed
            "refine_search",
            "execute_search",
            # Exploration
            "get_area_statistics",
        ]

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate evaluation context."""
        # Check if we have parcels to evaluate
        search_state = context.working.get("search_state", {})
        if not search_state.get("current_results"):
            return "No parcels available to evaluate. Run search first."
        return None

    def post_process(
        self,
        result: EvaluationOutput,
        context: SkillContext
    ) -> EvaluationOutput:
        """Determine if user made a selection."""
        # If user selected a parcel, suggest moving to negotiation
        if result.selection_made:
            result.suggested_action = "move_to_negotiation"
        elif result.user_liked:
            result.suggested_action = "show_more_details"
        elif result.user_rejected:
            result.suggested_action = "find_alternatives"
        else:
            result.suggested_action = "continue_evaluation"

        return result
