from typing import Any, Dict, List, Optional, TypedDict, Literal, Annotated
import operator

class ReviewState(TypedDict):
    """Shared state."""
    code: str
    filename: str
    review_id: str
    agent_run_mode: str

    # Coordinator phase control
    phase: Literal["planning", "consolidating", "done"]

    # Plan
    plan: Dict[str, Any]

    # Findings from parallel agents (use reducers so partial updates merge safely)
    security_findings: Annotated[List[Dict[str, Any]], operator.add]
    security_fixes: Annotated[List[Dict[str, Any]], operator.add]
    bug_findings: Annotated[List[Dict[str, Any]], operator.add]
    bug_fixes: Annotated[List[Dict[str, Any]], operator.add]

    # Join-barrier counter (each branch returns completed_agents=1)
    bug_agent_completed: bool
    security_agent_completed: bool

    # Final merged results
    final_findings: List[Dict[str, Any]]
    final_fixes: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    step_ids: set[str]

    # Metadata
    start_time: float
    errors: List[str]
