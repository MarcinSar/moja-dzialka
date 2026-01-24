"""
Discovery Skill - Requirements gathering through natural conversation.

This skill handles the DISCOVERY phase of the funnel:
- Collects location preferences
- Understands budget constraints
- Identifies feature priorities
- Determines when ready to search
"""

from typing import List, Optional, Type
from pydantic import BaseModel, Field

from ._base import ToolCallingSkill, SkillContext


class DiscoveryOutput(BaseModel):
    """Structured output from discovery skill."""

    # Internal reasoning
    thinking: str = Field(
        default="",
        description="Internal reasoning about user needs"
    )

    # Response to user
    ai_response: str = Field(
        default="",
        description="Natural language response to user"
    )

    # Extracted information
    location_extracted: Optional[str] = Field(
        default=None,
        description="Location mentioned (city, district, or area)"
    )
    budget_extracted: Optional[int] = Field(
        default=None,
        description="Budget amount in PLN if mentioned"
    )
    size_extracted: Optional[int] = Field(
        default=None,
        description="Desired size in m² if mentioned"
    )
    priorities_extracted: List[str] = Field(
        default_factory=list,
        description="Feature priorities mentioned (e.g., 'quiet', 'nature', 'schools')"
    )

    # Tracking
    fields_collected: List[str] = Field(
        default_factory=list,
        description="Fields successfully collected this turn"
    )
    fields_missing: List[str] = Field(
        default_factory=list,
        description="Fields still needed before search"
    )
    ready_for_search: bool = Field(
        default=False,
        description="True if enough info to start search"
    )

    # Next action suggestion
    next_action: Optional[str] = Field(
        default=None,
        description="Suggested next action for coordinator"
    )


class DiscoverySkill(ToolCallingSkill):
    """Gather buyer requirements through natural conversation."""

    @property
    def name(self) -> str:
        return "discovery"

    @property
    def description(self) -> str:
        return "Gather buyer requirements through natural conversation"

    @property
    def output_model(self) -> Type[BaseModel]:
        return DiscoveryOutput

    @property
    def available_tools(self) -> List[str]:
        """Tools available during discovery."""
        return [
            # Exploration tools
            "explore_administrative_hierarchy",
            "get_area_statistics",
            "get_gmina_info",
            "get_district_prices",
            "get_mpzp_symbols",
            # Can propose search when ready
            "propose_search_preferences",
            "count_matching_parcels",
        ]

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate discovery context."""
        if not context.user_message:
            return "User message is required for discovery"
        return None

    def post_process(
        self,
        result: DiscoveryOutput,
        context: SkillContext
    ) -> DiscoveryOutput:
        """Determine if ready for search based on collected info."""
        # Check what we have
        has_location = bool(result.location_extracted)
        has_budget = bool(result.budget_extracted)
        has_size = bool(result.size_extracted)
        has_priorities = len(result.priorities_extracted) > 0

        # Track what's collected
        if has_location:
            result.fields_collected.append("location")
        if has_budget:
            result.fields_collected.append("budget")
        if has_size:
            result.fields_collected.append("size")
        if has_priorities:
            result.fields_collected.append("priorities")

        # Determine what's missing
        result.fields_missing = []
        if not has_location:
            result.fields_missing.append("location")

        # Ready for search if we have location + at least one other criterion
        result.ready_for_search = (
            has_location and
            (has_budget or has_size or has_priorities)
        )

        # Suggest next action
        if result.ready_for_search:
            result.next_action = "propose_search_preferences"
        elif not has_location:
            result.next_action = "ask_location"
        else:
            result.next_action = "ask_preferences"

        return result
