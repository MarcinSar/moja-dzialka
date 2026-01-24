"""
Semantic Memory - Long-term User Profile.

Persisted knowledge about the buyer that survives sessions.
Extracted from conversations and updated over time.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime


class BuyerProfile(BaseModel):
    """Long-term buyer information extracted from conversations.

    This builds up over multiple sessions.
    """
    # Contact info (lead capture)
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Budget (PLN)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_confidence: float = 0.0  # 0-1, how sure we are about budget

    # Location preferences
    preferred_cities: List[str] = Field(default_factory=list)  # ["Gdańsk", "Gdynia"]
    preferred_districts: List[str] = Field(default_factory=list)  # ["Osowa", "Jasień"]
    avoided_districts: List[str] = Field(default_factory=list)  # ["Śródmieście"]

    # Size preferences (m²)
    size_m2_min: Optional[int] = None
    size_m2_max: Optional[int] = None
    preferred_size_category: Optional[str] = None  # "pod_dom", "duza", etc.

    # Feature priorities (inferred from conversation, 0-1 scale)
    priority_quietness: float = 0.5
    priority_nature: float = 0.3
    priority_accessibility: float = 0.2
    priority_schools: bool = False  # Has children
    priority_transport: bool = False  # Commutes
    priority_shops: bool = False

    # Use case
    purpose: Optional[str] = None  # "dom_jednorodzinny", "inwestycja", "rekreacja"
    building_plans: Optional[str] = None  # "budowa_od_zera", "dom_z_projektu", "kupno_z_domem"

    # Timeline
    urgency: Optional[str] = None  # "pilne", "w_tym_roku", "bez_pośpiechu"
    purchase_horizon: Optional[str] = None  # "1-3_miesiace", "pol_roku", "rok_plus"

    def update_priority(self, feature: str, value: float) -> None:
        """Update a priority value (clamped to 0-1)."""
        value = max(0.0, min(1.0, value))
        if feature == "quietness":
            self.priority_quietness = value
        elif feature == "nature":
            self.priority_nature = value
        elif feature == "accessibility":
            self.priority_accessibility = value


class InvestmentStrategy(BaseModel):
    """Investment goals and strategy (for investor profiles).

    Not all users are investors - many are just buying for themselves.
    """
    is_investor: bool = False
    strategy_type: Optional[str] = None  # "buy_and_hold", "flip", "rental", "development"
    expected_roi: Optional[float] = None  # percentage
    timeline: Optional[str] = None  # "short" (<1y), "medium" (1-5y), "long" (>5y)
    risk_tolerance: str = "moderate"  # "conservative", "moderate", "aggressive"
    previous_investments: int = 0  # Number of previous property investments


class SemanticMemory(BaseModel):
    """Long-term user knowledge.

    This persists across sessions and is updated incrementally.
    """
    buyer_profile: BuyerProfile = Field(default_factory=BuyerProfile)
    investment_strategy: InvestmentStrategy = Field(default_factory=InvestmentStrategy)

    # Session tracking
    first_visit: Optional[date] = None
    last_visit: Optional[date] = None
    total_sessions: int = 0
    total_searches: int = 0

    # Engagement signals
    engagement_score: float = 0.0  # 0-1, based on activity
    intent_signals: List[str] = Field(default_factory=list)  # ["asked_about_price", "saved_parcel"]

    # Known facts (extracted from conversation)
    known_facts: List[str] = Field(default_factory=list)  # ["has_children", "works_in_gdansk"]

    def increment_session(self) -> None:
        """Called when user starts a new session."""
        today = date.today()
        if self.first_visit is None:
            self.first_visit = today
        self.last_visit = today
        self.total_sessions += 1

    def add_intent_signal(self, signal: str) -> None:
        """Add an intent signal (deduplicated)."""
        if signal not in self.intent_signals:
            self.intent_signals.append(signal)
            self._update_engagement()

    def add_known_fact(self, fact: str) -> None:
        """Add a known fact about the user."""
        if fact not in self.known_facts:
            self.known_facts.append(fact)

    def _update_engagement(self) -> None:
        """Update engagement score based on signals."""
        # Simple scoring based on activity
        base_score = min(self.total_sessions * 0.1, 0.3)
        search_score = min(self.total_searches * 0.05, 0.2)
        intent_score = min(len(self.intent_signals) * 0.1, 0.5)
        self.engagement_score = min(base_score + search_score + intent_score, 1.0)
