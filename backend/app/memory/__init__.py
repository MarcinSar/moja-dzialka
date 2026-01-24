"""
7-layer memory model for moja-dzialka agent.

Based on Software 3.0 patterns for AI agents:
- Constitutional Memory (Core): Agent DNA, immutable
- Working Memory: Current session state
- Semantic Memory: Long-term user profile
- Episodic Memory: Compressed history
- Workflow Memory: Funnel state machine
- Preferences Memory: AI-managed style
- Procedural Memory: Skills registry reference
"""

from .schemas import (
    AgentState,
    PropertyAdvisorCore,
    WorkingMemory,
    SemanticMemory,
    EpisodicMemory,
    WorkflowMemory,
    AgentPreferences,
    FunnelPhase,
    SearchState,
    BuyerProfile,
    InvestmentStrategy,
)

from .logic.manager import MemoryManager
from .logic.compressor import SessionCompressor

__all__ = [
    # Main state
    "AgentState",
    # Core schemas
    "PropertyAdvisorCore",
    "WorkingMemory",
    "SemanticMemory",
    "EpisodicMemory",
    "WorkflowMemory",
    "AgentPreferences",
    # Enums and helpers
    "FunnelPhase",
    "SearchState",
    "BuyerProfile",
    "InvestmentStrategy",
    # Logic
    "MemoryManager",
    "SessionCompressor",
]
