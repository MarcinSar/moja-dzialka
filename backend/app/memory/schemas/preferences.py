"""
Preferences Memory - AI-Managed Style.

Stores preferences about how the agent should interact with this user.
Adapted over time based on user behavior and feedback.
"""

from pydantic import BaseModel, Field


class AdvisoryStyle(BaseModel):
    """AI-adapted advisor style based on user sophistication.

    Adjusts how technical/detailed the agent should be.
    """
    # Detail level in explanations
    detail_level: str = "moderate"  # "brief", "moderate", "comprehensive"

    # Use of real estate jargon
    jargon_usage: str = "low"  # "low", "moderate", "high"

    # How proactively to share price information
    price_transparency: str = "proactive"  # "reactive", "balanced", "proactive"

    # Whether to explain trade-offs
    explain_tradeoffs: bool = True

    # Focus areas (what to emphasize)
    emphasize_quietness: bool = False
    emphasize_nature: bool = False
    emphasize_accessibility: bool = False
    emphasize_investment: bool = False


class InteractionPreference(BaseModel):
    """How user prefers to interact.

    Learned from conversation patterns.
    """
    # Conversation pace
    pace: str = "moderate"  # "slow", "moderate", "fast"

    # Preferred format
    format: str = "conversational"  # "conversational", "structured", "data-focused"

    # Response length preference
    response_length: str = "medium"  # "short", "medium", "long"

    # Whether user prefers lists/bullets
    prefers_lists: bool = True

    # Whether user asks follow-up questions often
    is_inquisitive: bool = True

    # Language formality
    formality: str = "casual"  # "formal", "casual", "very_casual"


class AgentPreferences(BaseModel):
    """AI-managed preferences for this user.

    These are inferred and adapted, not explicitly set by user.
    """
    advisory_style: AdvisoryStyle = Field(default_factory=AdvisoryStyle)
    interaction_preference: InteractionPreference = Field(default_factory=InteractionPreference)

    # Presentation preferences
    parcels_per_presentation: int = 3  # How many to show at once
    show_price_estimates: bool = True  # Always show price estimates?
    show_scores: bool = True  # Show quietness/nature/accessibility scores?
    proactive_suggestions: bool = True  # Proactively suggest alternatives?

    # Map preferences
    auto_show_map: bool = True  # Automatically show map with results?

    # Notification preferences (for future use)
    wants_notifications: bool = False
    notification_frequency: str = "weekly"  # "daily", "weekly", "monthly"

    def adapt_to_user_message(self, message: str) -> None:
        """Adapt preferences based on user message patterns."""
        message_lower = message.lower()

        # Detect pace preference
        if len(message) < 20:
            # Short messages = probably wants concise responses
            self.interaction_preference.response_length = "short"
        elif len(message) > 200:
            # Long messages = probably okay with longer responses
            self.interaction_preference.response_length = "long"

        # Detect jargon comfort
        jargon_words = ["mpzp", "pog", "strefa", "zabudowa", "kondygnacja", "użytkowa"]
        if any(word in message_lower for word in jargon_words):
            self.advisory_style.jargon_usage = "moderate"

        # Detect investment focus
        investment_words = ["inwestycja", "zwrot", "roi", "wynajem", "flipować"]
        if any(word in message_lower for word in investment_words):
            self.advisory_style.emphasize_investment = True

        # Detect nature/quiet focus
        nature_words = ["las", "natura", "zieleń", "cisza", "spokój", "cicho"]
        if any(word in message_lower for word in nature_words):
            self.advisory_style.emphasize_nature = True
            self.advisory_style.emphasize_quietness = True

        # Detect data-focused user
        data_words = ["statystyki", "dane", "liczby", "konkretnie", "dokładnie"]
        if any(word in message_lower for word in data_words):
            self.interaction_preference.format = "data-focused"
            self.advisory_style.detail_level = "comprehensive"

    def get_prompt_modifiers(self) -> dict:
        """Get prompt modifiers based on preferences."""
        return {
            "response_length": self.interaction_preference.response_length,
            "use_jargon": self.advisory_style.jargon_usage != "low",
            "show_prices": self.show_price_estimates,
            "explain_tradeoffs": self.advisory_style.explain_tradeoffs,
            "emphasis": {
                "quietness": self.advisory_style.emphasize_quietness,
                "nature": self.advisory_style.emphasize_nature,
                "accessibility": self.advisory_style.emphasize_accessibility,
                "investment": self.advisory_style.emphasize_investment,
            },
        }
