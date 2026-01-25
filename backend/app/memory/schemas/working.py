"""
Working Memory - Current Session State.

Volatile memory that tracks the current conversation.
Uses a sliding window to prevent context rot.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class FunnelPhase(str, Enum):
    """Sales funnel phases - explicit state machine.

    The agent progresses through these phases:
    DISCOVERY → SEARCH → EVALUATION → NEGOTIATION → LEAD_CAPTURE

    Users can also be in RETENTION phase (returning visitors).
    """
    DISCOVERY = "DISCOVERY"           # Zbieranie wymagań
    SEARCH = "SEARCH"                 # Wyszukiwanie działek
    EVALUATION = "EVALUATION"         # Porównywanie opcji
    NEGOTIATION = "NEGOTIATION"       # Dyskusja o cenie/warunkach
    LEAD_CAPTURE = "LEAD_CAPTURE"     # Zbieranie kontaktu
    RETENTION = "RETENTION"           # Powracający użytkownik


class SearchState(BaseModel):
    """Current search state within session.

    Tracks the propose → approve → execute flow.
    """
    preferences_proposed: bool = False
    preferences_approved: bool = False
    search_executed: bool = False
    results_shown: int = 0

    # Current search preferences (perceived → approved)
    perceived_preferences: Optional[Dict[str, Any]] = None
    approved_preferences: Optional[Dict[str, Any]] = None

    # Search results and feedback (for critic pattern)
    current_results: List[Dict[str, Any]] = Field(default_factory=list)
    search_feedback: Optional[str] = None
    search_iteration: int = 0

    # Index map: position (1, 2, 3...) → parcel ID
    # Allows user to say "pokaż działkę 1" instead of full ID
    parcel_index_map: Dict[int, str] = Field(default_factory=dict)

    # Selected parcels
    favorited_parcels: List[str] = Field(default_factory=list)
    rejected_parcels: List[str] = Field(default_factory=list)


class Message(BaseModel):
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional metadata
    tool_calls: Optional[List[Dict[str, Any]]] = None
    extracted_info: Optional[Dict[str, Any]] = None


class WorkingMemory(BaseModel):
    """Current session state (volatile).

    This is the "hot" memory that changes during conversation.
    Uses sliding window to prevent context rot (n² problem).
    """
    session_id: str
    current_phase: FunnelPhase = FunnelPhase.DISCOVERY
    search_state: SearchState = Field(default_factory=SearchState)

    # Conversation buffer (sliding window - last N messages)
    conversation_buffer: List[Message] = Field(default_factory=list)
    max_buffer_size: int = 20  # Sliding window size

    # Temporary variables for current interaction
    temp_vars: Dict[str, Any] = Field(default_factory=dict)

    # Current skill being executed
    active_skill: Optional[str] = None

    # Session timestamps
    session_start: datetime = Field(default_factory=datetime.utcnow)
    last_message: Optional[datetime] = None

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """Add message and maintain sliding window."""
        msg = Message(role=role, content=content, **kwargs)
        self.conversation_buffer.append(msg)
        self.last_message = msg.timestamp

        # Maintain sliding window
        if len(self.conversation_buffer) > self.max_buffer_size:
            # Keep last N messages
            self.conversation_buffer = self.conversation_buffer[-self.max_buffer_size:]

        return msg

    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """Get messages in Claude API format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.conversation_buffer
        ]

    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message."""
        for msg in reversed(self.conversation_buffer):
            if msg.role == "user":
                return msg.content
        return None

    def clear_temp_vars(self) -> None:
        """Clear temporary variables (between turns)."""
        self.temp_vars = {}

    def transition_to(self, phase: FunnelPhase) -> None:
        """Transition to a new funnel phase."""
        self.current_phase = phase
        # Reset skill when changing phase
        self.active_skill = None
