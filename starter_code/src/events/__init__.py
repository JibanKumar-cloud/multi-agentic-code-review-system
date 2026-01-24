"""
Events module - Provides event types and event bus for the system.
"""

from .event_types import (
    Event,
    EventType,
    Severity,
    FindingCategory,
    Location,
    Finding,
    Fix,
    PlanStep,
    create_review_started_event,
    create_plan_created_event,
    create_plan_step_started_event,
    create_plan_step_completed_event,
    create_agent_started_event,
    create_agent_completed_event,
    create_agent_error_event,
    create_thinking_event,
    create_thinking_complete_event,
    create_tool_call_start_event,
    create_tool_call_result_event,
    create_finding_discovered_event,
    create_fix_proposed_event,
    create_fix_verified_event,
    create_findings_consolidated_event,
    create_final_report_event,
)

from .event_bus import EventBus, event_bus

__all__ = [
    # Types
    "Event",
    "EventType",
    "Severity",
    "FindingCategory",
    "Location",
    "Finding",
    "Fix",
    "PlanStep",
    # Event Bus
    "EventBus",
    "event_bus",
    # Factory functions
    "create_review_started_event",
    "create_plan_created_event",
    "create_plan_step_started_event",
    "create_plan_step_completed_event",
    "create_agent_started_event",
    "create_agent_completed_event",
    "create_agent_error_event",
    "create_thinking_event",
    "create_thinking_complete_event",
    "create_tool_call_start_event",
    "create_tool_call_result_event",
    "create_finding_discovered_event",
    "create_fix_proposed_event",
    "create_fix_verified_event",
    "create_findings_consolidated_event",
    "create_final_report_event",
]
