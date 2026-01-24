"""
Search Skill - Property search execution.

This skill handles the SEARCH phase of the funnel:
- Proposes search preferences
- Executes search when approved
- Presents results to user
- Handles refinement based on feedback
"""

from typing import List, Optional, Type, Dict, Any
from pydantic import BaseModel, Field

from ._base import ToolCallingSkill, SkillContext


class ParcelSummary(BaseModel):
    """Summary of a parcel for presentation."""
    id: str
    gmina: Optional[str] = None
    dzielnica: Optional[str] = None
    area_m2: Optional[float] = None
    quietness_score: Optional[float] = None
    nature_score: Optional[float] = None
    accessibility_score: Optional[float] = None
    estimated_price: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    explanation: Optional[str] = None


class SearchOutput(BaseModel):
    """Structured output from search skill."""

    # Internal reasoning
    thinking: str = Field(
        default="",
        description="Internal reasoning about search strategy"
    )

    # Response to user
    ai_response: str = Field(
        default="",
        description="Natural language response with results"
    )

    # Search state
    preferences_proposed: bool = Field(
        default=False,
        description="Whether preferences were proposed this turn"
    )
    preferences_approved: bool = Field(
        default=False,
        description="Whether preferences are approved"
    )
    search_executed: bool = Field(
        default=False,
        description="Whether search was executed this turn"
    )

    # Results
    results_count: int = Field(
        default=0,
        description="Number of parcels found"
    )
    results_shown: int = Field(
        default=0,
        description="Number of parcels shown to user"
    )
    top_parcels: List[ParcelSummary] = Field(
        default_factory=list,
        description="Top parcels to present"
    )

    # Map data
    map_center: Optional[Dict[str, float]] = Field(
        default=None,
        description="Center point for map display"
    )
    parcel_ids_for_map: List[str] = Field(
        default_factory=list,
        description="Parcel IDs to show on map"
    )

    # Next action
    needs_refinement: bool = Field(
        default=False,
        description="Whether user expressed dissatisfaction"
    )
    refinement_hint: Optional[str] = Field(
        default=None,
        description="Hint for how to refine search"
    )


class SearchSkill(ToolCallingSkill):
    """Execute property search based on preferences."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for properties matching user preferences"

    @property
    def output_model(self) -> Type[BaseModel]:
        return SearchOutput

    @property
    def available_tools(self) -> List[str]:
        """Tools available during search."""
        return [
            # Core search tools
            "propose_search_preferences",
            "approve_search_preferences",
            "modify_search_preferences",
            "execute_search",
            "count_matching_parcels",
            # Refinement
            "critique_search_results",
            "refine_search",
            # Similar/spatial
            "find_similar_parcels",
            "search_around_point",
            "search_in_bbox",
            # Info
            "get_parcel_details",
            "get_parcel_neighborhood",
            # Map
            "generate_map_data",
            # Price
            "get_district_prices",
            "estimate_parcel_value",
        ]

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate search context."""
        # Search can proceed with or without explicit user message
        # (e.g., after auto-approval)
        return None

    def post_process(
        self,
        result: SearchOutput,
        context: SkillContext
    ) -> SearchOutput:
        """Add map data if parcels were found."""
        if result.top_parcels:
            result.parcel_ids_for_map = [p.id for p in result.top_parcels]

            # Calculate center from first parcel (if we had coordinates)
            # In real implementation, this would come from the parcels

        return result
