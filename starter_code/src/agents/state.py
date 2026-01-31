from typing import Any, Dict, List, Optional, TypedDict, Literal, Annotated, Set
import operator

class ReviewState(TypedDict):
    # Core
    code: str
    filename: str
    review_id: str
    agent_run_mode: str

    # Coordinator phase control
    phase: Literal["planning", "executing", "done"]

    # Plan
    plan: Dict[str, Any]

    # Parallel outputs (merge safely)
    security_findings: Annotated[List[Dict[str, Any]], operator.add]
    security_fixes: Annotated[List[Dict[str, Any]], operator.add]
    bug_findings: Annotated[List[Dict[str, Any]], operator.add]
    bug_fixes: Annotated[List[Dict[str, Any]], operator.add]

    # Completion flags (IMPORTANT: ensure only the owning node writes these)
    bug_agent_completed: bool
    security_agent_completed: bool

    # Final merged results
    final_findings: List[Dict[str, Any]]
    final_fixes: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]

    # If multiple nodes add step_ids, make it a reducer too (recommended)
    step_ids: Annotated[Set[str], operator.or_]

    # Metadata
    start_time: float

    # MUST be reducer if multiple nodes append errors in parallel
    # Prefer dicts for structure (agent, type, message, attempt, etc.)
    errors: Annotated[List[Dict[str, Any]], operator.add]
