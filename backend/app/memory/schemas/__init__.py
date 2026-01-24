"""
Pydantic schemas for 7-layer memory model.
"""

from .core import PropertyAdvisorCore
from .working import WorkingMemory, FunnelPhase, SearchState
from .semantic import SemanticMemory, BuyerProfile, InvestmentStrategy
from .episodic import EpisodicMemory, SearchSession, SearchPattern
from .workflow import WorkflowMemory, FunnelProgress
from .preferences import AgentPreferences, AdvisoryStyle, InteractionPreference

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class AgentState(BaseModel):
    """Complete agent state for one user session.

    Combines all 7 memory layers into a single serializable state.
    This state is persisted per-user via Redis (hot) + PostgreSQL (cold).
    """
    # User identification
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Memory layers
    core: PropertyAdvisorCore = Field(default_factory=PropertyAdvisorCore)
    working: WorkingMemory = Field(default_factory=lambda: WorkingMemory(session_id=str(uuid.uuid4())))
    semantic: SemanticMemory = Field(default_factory=SemanticMemory)
    episodic: EpisodicMemory = Field(default_factory=EpisodicMemory)
    workflow: WorkflowMemory = Field(default_factory=lambda: WorkflowMemory(
        visitor_id=str(uuid.uuid4()),
        first_visit=datetime.utcnow(),
        last_activity=datetime.utcnow()
    ))
    preferences: AgentPreferences = Field(default_factory=AgentPreferences)

    class Config:
        arbitrary_types_allowed = True

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.updated_at = datetime.utcnow()
        self.workflow.last_activity = datetime.utcnow()

    def to_context_dict(self) -> dict:
        """Convert to dict suitable for Jinja2 template rendering.

        Note: Returns actual Pydantic model objects (not dicts) so that
        templates can call methods like workflow.funnel_progress.is_ready_for_search().
        """
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "core": self.core,
            "working": self.working,
            "semantic": self.semantic,
            "episodic": self.episodic,
            "workflow": self.workflow,
            "preferences": self.preferences,
        }


__all__ = [
    # Main state
    "AgentState",
    # Core
    "PropertyAdvisorCore",
    # Working
    "WorkingMemory",
    "FunnelPhase",
    "SearchState",
    # Semantic
    "SemanticMemory",
    "BuyerProfile",
    "InvestmentStrategy",
    # Episodic
    "EpisodicMemory",
    "SearchSession",
    "SearchPattern",
    # Workflow
    "WorkflowMemory",
    "FunnelProgress",
    # Preferences
    "AgentPreferences",
    "AdvisoryStyle",
    "InteractionPreference",
]
