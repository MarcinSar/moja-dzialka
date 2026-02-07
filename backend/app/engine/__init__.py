"""
Agent Engine - Single agent with notepad-driven flow (v4)
+ legacy multi-agent system (v2/v3) for backward compatibility.

v4 Architecture:
- Agent: Single agent loop with streaming
- Session: Conversation state + notepad injection
- Notepad: Session state shared between agent and backend
- ToolExecutorV4: 16 consolidated tools
- ToolGates: Middleware for tool prerequisites

Legacy (v2/v3, kept for backward compat):
- AgentCoordinator: Routing + State Management
- PropertyAdvisorAgent: Skill Execution (Root Orchestrator)
- SubAgentSpawner: Multi-agent orchestration
"""

# v4 - New architecture
from .agent import Agent
from .session import Session
from .notepad import Notepad, LocationState, SearchResults
from .tool_executor_v4 import ToolExecutorV4
from .tool_gates import check_gates
from .tool_definitions import get_tool_definitions
from .prompt_compiler import get_system_prompt
from . import result_store

# v2/v3 - Legacy (still used by conversation_v2.py)
from .agent_coordinator import AgentCoordinator
from .property_advisor_agent import PropertyAdvisorAgent
from .sub_agents import (
    SubAgentSpawner,
    AgentRouter,
    AgentType,
    AgentConfig,
    ModelType,
    SubAgentResult,
    AGENT_CONFIGS,
    DEFAULT_MODEL_CONFIG,
    create_sub_agent_spawner,
)

__all__ = [
    # v4
    "Agent",
    "Session",
    "Notepad",
    "LocationState",
    "SearchResults",
    "ToolExecutorV4",
    "check_gates",
    "get_tool_definitions",
    "get_system_prompt",
    "result_store",
    # v2/v3 legacy
    "AgentCoordinator",
    "PropertyAdvisorAgent",
    "SubAgentSpawner",
    "AgentRouter",
    "AgentType",
    "AgentConfig",
    "ModelType",
    "SubAgentResult",
    "AGENT_CONFIGS",
    "DEFAULT_MODEL_CONFIG",
    "create_sub_agent_spawner",
]
