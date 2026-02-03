"""
Tool Policies - Access control and rate limiting for tools.

Policy stack:
  Request → GuardPolicy → PhasePolicy → FreemiumPolicy → RateLimit → EXECUTE

Currently a skeleton for future freemium implementation.
All policies default to ALLOW for now.
"""

from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from loguru import logger

from app.memory import AgentState, FunnelPhase
from app.engine.tool_schema_v3 import PolicyTag, get_tool_registry_v3


class PolicyResult(str, Enum):
    """Result of policy evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    UPGRADE_REQUIRED = "upgrade_required"  # Freemium - needs payment


@dataclass
class PolicyDecision:
    """Result of evaluating all policies for a tool call."""
    result: PolicyResult
    tool_name: str
    reason: Optional[str] = None
    upgrade_message: Optional[str] = None
    remaining_quota: Optional[int] = None


@dataclass
class UserQuota:
    """Track user's usage quotas for rate limiting."""
    user_id: str
    searches_today: int = 0
    parcels_revealed_today: int = 0
    detail_views_today: int = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    def reset_if_needed(self) -> None:
        """Reset quotas if it's a new day."""
        now = datetime.utcnow()
        if (now - self.last_reset) > timedelta(hours=24):
            self.searches_today = 0
            self.parcels_revealed_today = 0
            self.detail_views_today = 0
            self.last_reset = now


# =============================================================================
# POLICY IMPLEMENTATIONS
# =============================================================================

class GuardPolicy:
    """Check tool prerequisites (e.g., preferences must be proposed before approve)."""

    # Tool → required state conditions
    GUARDS = {
        "approve_search_preferences": lambda s: s.working.search_state.preferences_proposed,
        "execute_search": lambda s: s.working.search_state.preferences_approved,
        "refine_search": lambda s: s.working.search_state.search_executed,
    }

    @classmethod
    def evaluate(cls, tool_name: str, state: AgentState) -> PolicyDecision:
        """Evaluate guard policy for a tool."""
        guard = cls.GUARDS.get(tool_name)

        if guard is None:
            return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        if guard(state):
            return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        return PolicyDecision(
            result=PolicyResult.DENY,
            tool_name=tool_name,
            reason=f"Warunek wstępny nie spełniony dla {tool_name}",
        )


class PhasePolicy:
    """Check if tool is allowed in current funnel phase."""

    # Phase → allowed tool categories
    PHASE_TOOLS = {
        FunnelPhase.DISCOVERY: {"preference", "location", "general"},
        FunnelPhase.SEARCH: {"preference", "search", "location", "general"},
        FunnelPhase.EVALUATION: {"context", "comparison", "pricing", "search", "general"},
        FunnelPhase.NEGOTIATION: {"context", "pricing", "lead", "general"},
        FunnelPhase.LEAD_CAPTURE: {"lead", "general"},
        FunnelPhase.RETENTION: {"preference", "search", "context", "general"},
    }

    @classmethod
    def evaluate(cls, tool_name: str, state: AgentState) -> PolicyDecision:
        """Evaluate phase policy for a tool."""
        registry = get_tool_registry_v3()
        tool = registry.get(tool_name)

        if tool is None:
            # Tool not in V3 registry - allow (backward compatibility)
            return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        current_phase = state.working.current_phase
        allowed_categories = cls.PHASE_TOOLS.get(current_phase, {"general"})

        if tool.category in allowed_categories:
            return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        return PolicyDecision(
            result=PolicyResult.DENY,
            tool_name=tool_name,
            reason=f"Narzędzie {tool_name} niedostępne w fazie {current_phase.value}",
        )


class FreemiumPolicy:
    """Check freemium access (currently disabled - all tools allowed)."""

    # Free tier limits (for future implementation)
    FREE_LIMITS = {
        "searches_per_day": 10,
        "parcels_revealed": 3,
        "detail_views_per_day": 10,
    }

    # Premium-only tools
    PREMIUM_TOOLS = {
        "generate_terrain_3d",
        "get_historical_prices",
        "calculate_investment_score",
    }

    @classmethod
    def evaluate(
        cls,
        tool_name: str,
        state: AgentState,
        user_tier: str = "free",
    ) -> PolicyDecision:
        """Evaluate freemium policy for a tool.

        Currently returns ALLOW for all tools.
        Enable freemium by uncommenting the checks below.
        """
        # FREEMIUM DISABLED - uncomment when ready
        return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        # --- FREEMIUM LOGIC (disabled) ---
        # if user_tier == "paid":
        #     return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)
        #
        # if tool_name in cls.PREMIUM_TOOLS:
        #     return PolicyDecision(
        #         result=PolicyResult.UPGRADE_REQUIRED,
        #         tool_name=tool_name,
        #         reason=f"Narzędzie {tool_name} wymaga płatnego pakietu",
        #         upgrade_message="Odblokuj premium narzędzia za 20 PLN",
        #     )
        #
        # return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)


class RateLimitPolicy:
    """Rate limiting for tools (currently disabled)."""

    # In-memory quota storage (would be Redis in production)
    _quotas: Dict[str, UserQuota] = {}

    @classmethod
    def get_quota(cls, user_id: str) -> UserQuota:
        """Get or create user quota."""
        if user_id not in cls._quotas:
            cls._quotas[user_id] = UserQuota(user_id=user_id)
        quota = cls._quotas[user_id]
        quota.reset_if_needed()
        return quota

    @classmethod
    def evaluate(
        cls,
        tool_name: str,
        state: AgentState,
        user_tier: str = "free",
    ) -> PolicyDecision:
        """Evaluate rate limit policy for a tool.

        Currently returns ALLOW for all tools.
        Enable rate limiting by uncommenting the checks below.
        """
        # RATE LIMITING DISABLED - uncomment when ready
        return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)

        # --- RATE LIMIT LOGIC (disabled) ---
        # if user_tier == "paid":
        #     return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)
        #
        # quota = cls.get_quota(state.user_id)
        #
        # if tool_name == "execute_search":
        #     if quota.searches_today >= FreemiumPolicy.FREE_LIMITS["searches_per_day"]:
        #         return PolicyDecision(
        #             result=PolicyResult.UPGRADE_REQUIRED,
        #             tool_name=tool_name,
        #             reason="Limit wyszukiwań osiągnięty",
        #             remaining_quota=0,
        #         )
        #     quota.searches_today += 1
        #
        # return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)


# =============================================================================
# POLICY STACK
# =============================================================================

class PolicyStack:
    """Evaluate all policies in order.

    Request → GuardPolicy → PhasePolicy → FreemiumPolicy → RateLimit → EXECUTE
    """

    @classmethod
    def evaluate(
        cls,
        tool_name: str,
        state: AgentState,
        user_tier: str = "free",
    ) -> PolicyDecision:
        """Evaluate all policies for a tool call.

        Returns the first DENY/UPGRADE_REQUIRED decision,
        or ALLOW if all policies pass.
        """
        # 1. Guard policy (prerequisites)
        decision = GuardPolicy.evaluate(tool_name, state)
        if decision.result != PolicyResult.ALLOW:
            logger.debug(f"Policy DENY (guard): {tool_name} - {decision.reason}")
            return decision

        # 2. Phase policy (funnel state)
        decision = PhasePolicy.evaluate(tool_name, state)
        if decision.result != PolicyResult.ALLOW:
            logger.debug(f"Policy DENY (phase): {tool_name} - {decision.reason}")
            return decision

        # 3. Freemium policy
        decision = FreemiumPolicy.evaluate(tool_name, state, user_tier)
        if decision.result != PolicyResult.ALLOW:
            logger.debug(f"Policy DENY (freemium): {tool_name} - {decision.reason}")
            return decision

        # 4. Rate limit policy
        decision = RateLimitPolicy.evaluate(tool_name, state, user_tier)
        if decision.result != PolicyResult.ALLOW:
            logger.debug(f"Policy DENY (rate_limit): {tool_name} - {decision.reason}")
            return decision

        # All policies passed
        return PolicyDecision(result=PolicyResult.ALLOW, tool_name=tool_name)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_tool_access(
    tool_name: str,
    state: AgentState,
    user_tier: str = "free",
) -> Tuple[bool, Optional[str]]:
    """Check if a tool can be executed.

    Args:
        tool_name: Name of the tool
        state: Current agent state
        user_tier: User's payment tier

    Returns:
        Tuple of (allowed, error_message)
    """
    decision = PolicyStack.evaluate(tool_name, state, user_tier)

    if decision.result == PolicyResult.ALLOW:
        return True, None

    if decision.result == PolicyResult.UPGRADE_REQUIRED:
        return False, decision.upgrade_message or decision.reason

    return False, decision.reason


def get_available_tools(
    state: AgentState,
    user_tier: str = "free",
) -> List[str]:
    """Get list of tools available to the user in current state.

    Args:
        state: Current agent state
        user_tier: User's payment tier

    Returns:
        List of tool names that pass all policies
    """
    registry = get_tool_registry_v3()
    available = []

    for tool_name in registry.list_tools():
        allowed, _ = check_tool_access(tool_name, state, user_tier)
        if allowed:
            available.append(tool_name)

    return available
