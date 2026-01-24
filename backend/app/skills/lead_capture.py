"""
Lead Capture Skill - Contact information collection.

This skill handles the LEAD_CAPTURE phase:
- Encourages leaving contact info
- Presents package options
- Captures email/phone
- Schedules follow-up
"""

from typing import List, Optional, Type
from pydantic import BaseModel, Field
import re

from ._base import Skill, SkillContext


class LeadCaptureOutput(BaseModel):
    """Structured output from lead capture skill."""

    # Internal reasoning
    thinking: str = Field(
        default="",
        description="Internal reasoning about lead capture"
    )

    # Response to user
    ai_response: str = Field(
        default="",
        description="Natural language response"
    )

    # Contact info extracted
    name: Optional[str] = Field(
        default=None,
        description="User's name if provided"
    )
    email: Optional[str] = Field(
        default=None,
        description="Email address if provided"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Phone number if provided"
    )

    # Contact status
    contact_captured: bool = Field(
        default=False,
        description="Whether any contact info was captured"
    )
    contact_method_preference: Optional[str] = Field(
        default=None,
        description="Preferred contact method"
    )

    # Package interest
    package_interest_shown: bool = Field(
        default=False,
        description="Whether user showed interest in packages"
    )
    preferred_package: Optional[str] = Field(
        default=None,
        description="Package user is interested in"
    )

    # Follow-up
    follow_up_requested: bool = Field(
        default=False,
        description="Whether user wants follow-up"
    )
    follow_up_timing: Optional[str] = Field(
        default=None,
        description="When to follow up"
    )

    # Next steps
    conversion_ready: bool = Field(
        default=False,
        description="Whether lead is ready for conversion"
    )
    suggested_action: Optional[str] = Field(
        default=None,
        description="Suggested next action"
    )


class LeadCaptureSkill(Skill):
    """Capture contact information and present packages."""

    @property
    def name(self) -> str:
        return "lead_capture"

    @property
    def description(self) -> str:
        return "Capture contact information and present packages"

    @property
    def output_model(self) -> Type[BaseModel]:
        return LeadCaptureOutput

    def validate_context(self, context: SkillContext) -> Optional[str]:
        """Validate lead capture context."""
        # Lead capture can run at any time
        return None

    def post_process(
        self,
        result: LeadCaptureOutput,
        context: SkillContext
    ) -> LeadCaptureOutput:
        """Validate and normalize contact info."""
        # Validate email format
        if result.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, result.email):
                result.email = None

        # Normalize phone number
        if result.phone:
            # Remove spaces, dashes, parentheses
            phone = re.sub(r'[\s\-\(\)]', '', result.phone)
            # Check if valid Polish number
            if len(phone) >= 9 and phone.replace('+', '').isdigit():
                result.phone = phone
            else:
                result.phone = None

        # Determine if contact was captured
        result.contact_captured = bool(result.email or result.phone)

        # Determine conversion readiness
        result.conversion_ready = (
            result.contact_captured and
            (result.package_interest_shown or result.follow_up_requested)
        )

        # Suggest next action
        if result.conversion_ready:
            result.suggested_action = "process_lead"
        elif result.contact_captured:
            result.suggested_action = "confirm_and_thank"
        elif context.workflow.get("funnel_progress", {}).get("favorites_count", 0) > 0:
            result.suggested_action = "remind_of_favorites"
        else:
            result.suggested_action = "soft_ask_contact"

        return result
