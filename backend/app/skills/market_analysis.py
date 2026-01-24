"""
Market Analysis Skill - Price and market insights.

This skill provides:
- Price estimates for parcels
- District price comparisons
- Market trends (conceptual)
- Investment potential analysis
"""

from typing import List, Optional, Type, Dict, Any
from pydantic import BaseModel, Field

from ._base import ToolCallingSkill, SkillContext


class DistrictPriceInfo(BaseModel):
    """Price information for a district."""
    city: str
    district: Optional[str] = None
    price_min: int
    price_max: int
    segment: str
    description: str


class ParcelValuation(BaseModel):
    """Valuation for a parcel."""
    parcel_id: Optional[str] = None
    city: str
    district: Optional[str] = None
    area_m2: float
    estimated_min: int
    estimated_max: int
    price_per_m2_range: str
    segment: str
    confidence: str


class MarketAnalysisOutput(BaseModel):
    """Structured output from market analysis skill."""

    # Internal reasoning
    thinking: str = Field(
        default="",
        description="Internal reasoning about market analysis"
    )

    # Response to user
    ai_response: str = Field(
        default="",
        description="Natural language market analysis"
    )

    # District prices
    district_prices: List[DistrictPriceInfo] = Field(
        default_factory=list,
        description="Price info for districts analyzed"
    )

    # Parcel valuations
    valuations: List[ParcelValuation] = Field(
        default_factory=list,
        description="Valuations for specific parcels"
    )

    # Comparison
    comparison_summary: Optional[str] = Field(
        default=None,
        description="Summary comparing different areas/prices"
    )

    # Recommendations
    budget_fit_districts: List[str] = Field(
        default_factory=list,
        description="Districts that fit user's budget"
    )
    value_opportunities: List[str] = Field(
        default_factory=list,
        description="Districts with good value"
    )

    # Investment perspective
    investment_insights: Optional[str] = Field(
        default=None,
        description="Investment-focused insights if relevant"
    )


class MarketAnalysisSkill(ToolCallingSkill):
    """Provide market analysis and price insights."""

    @property
    def name(self) -> str:
        return "market_analysis"

    @property
    def description(self) -> str:
        return "Provide market analysis and price insights"

    @property
    def output_model(self) -> Type[BaseModel]:
        return MarketAnalysisOutput

    @property
    def available_tools(self) -> List[str]:
        """Tools available for market analysis."""
        return [
            # Price tools
            "get_district_prices",
            "estimate_parcel_value",
            # Area info
            "get_area_statistics",
            "get_gmina_info",
            # Exploration
            "explore_administrative_hierarchy",
        ]

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate market analysis context."""
        # Market analysis can always run
        return None

    def post_process(
        self,
        result: MarketAnalysisOutput,
        context: SkillContext
    ) -> MarketAnalysisOutput:
        """Add budget-based recommendations."""
        # Get user's budget from semantic memory
        budget_max = context.semantic.get("buyer_profile", {}).get("budget_max")

        if budget_max and result.district_prices:
            # Find districts that fit budget
            for district in result.district_prices:
                # Calculate max area affordable
                if district.price_max > 0:
                    max_area = budget_max / district.price_max
                    if max_area >= 500:  # At least 500m² affordable
                        result.budget_fit_districts.append(
                            f"{district.district or district.city} (do {int(max_area)}m²)"
                        )

        return result
