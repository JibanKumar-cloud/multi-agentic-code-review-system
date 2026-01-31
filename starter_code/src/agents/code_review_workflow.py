import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Set, List
from langgraph.graph import StateGraph, END

from .state import ReviewState
from ..config import config
from ..events import (
    EventBus,
    create_review_started_event,
    create_plan_step_started_event,
    create_plan_step_completed_event
)


from ..utility.retry_utils import (RetryPolicy, 
                                validate_security_update,
                                validate_bug_update,
                                validate_coordinator_update,
                                run_node_with_retry,
                                retry_predicate,
                                retry_policy_for,
                                retry_lists_for
                                )


logger = logging.getLogger(__name__)



class CodeReviewWorkflow:
    """
    coordinator(planning) -> fanout -> [security, bug] (parallel) -> join(wait) -> coordinator(consolidating) -> END
    Each node is wrapped with retry + strict state-write hygiene.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        from . import CoordinatorAgent, SecurityAgent, BugDetectionAgent
        self.coordinator = CoordinatorAgent(event_bus)
        self.security_agent = SecurityAgent(event_bus)
        self.bug_agent = BugDetectionAgent(event_bus)

        self.graph = self._build_graph()
        self.app = self.graph.compile()

        # pull retry config (recommended structure)
        self.retry_cfg = getattr(config, "retry", {}) or {}


    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ReviewState)

        # Wrap nodes (critical: only wrapper sets completion flags)
        graph.add_node("coordinator", self._coordinator_node)
        graph.add_node("fanout", self._fanout_node)
        graph.add_node("security_agent", self._security_node)
        graph.add_node("bug_agent", self._bug_node)
        graph.add_node("join", self._join_node)

        graph.set_entry_point("coordinator")

        graph.add_conditional_edges(
            "coordinator",
            self._route_from_coordinator,
            {"fanout": "fanout", "end": END},
        )

        graph.add_edge("fanout", "security_agent")
        graph.add_edge("fanout", "bug_agent")

        graph.add_edge("security_agent", "join")
        graph.add_edge("bug_agent", "join")

        graph.add_conditional_edges(
            "join",
            self._route_from_join,
            {"wait": "join", "go": "coordinator"},
        )

        return graph

    async def _fanout_node(self, state: ReviewState) -> Dict[str, Any]:
        return {}

    async def _join_node(self, state: ReviewState) -> Dict[str, Any]:
        """
        Join barrier node - waits for both agents to complete.
        Small sleep prevents busy-loop CPU spikes while one agent is still running.
        """
        await asyncio.sleep(0.01)  # 10ms - keeps UI responsive and CPU calm
        return {}

    def _route_from_coordinator(self, state: ReviewState) -> str:
        """
        NO retries here. Pure routing.
        Coordinator node itself retries and/or sets fatal error state.
        """
        # planning -> fanout, anything else -> end
        if state.get("phase") == "executing" and state["plan"]:
            return "fanout"
        return "end"

    def _route_from_join(self, state: ReviewState) -> str:
        """
        Wait until both specialists finish, then go back to coordinator for consolidation.
        """
        return "go" if (state.get("bug_agent_completed") and state.get("security_agent_completed")) else "wait"



    async def review_code(self, code: str, filename: str = "code.py") -> Dict[str, Any]:
        review_id = str(uuid.uuid4())[:8]

        await self.event_bus.publish(
            create_review_started_event(review_id, filename, len(code.splitlines()))
        )

        initial_state: ReviewState = {
            "code": code,
            "filename": filename,
            "review_id": review_id,
            "agent_run_mode": "parallel",

            # must be one of: "planning" | "consolidating" | "done"
            "phase": "planning",

            "plan": {},

            # reducers (lists)
            "security_findings": [],
            "security_fixes": [],
            "bug_findings": [],
            "bug_fixes": [],

            # final outputs
            "final_findings": [],
            "final_fixes": [],
            "final_report": None,

            # metadata
            "start_time": time.time(),

            # reducer list (store dicts)
            "errors": [],

            # join flags
            "bug_agent_completed": False,
            "security_agent_completed": False,

            # reducer set (operator.or_)
            "step_ids": set(),
        }


        final_state = await self._run_graph(initial_state)
        return final_state.get("final_report") or {}

    async def _run_graph(self, state: ReviewState) -> ReviewState:
        try:
            return await self.app.ainvoke(state)
        except Exception as e:
            logger.exception(f"LangGraph ainvoke failed, fallback manual: {e}")
            # If you already have manual fallback, call it here.
            return dict(state, final_report={"status": "failed", "error": str(e)}, phase="done")


    async def _coordinator_node(self, state: ReviewState) -> Dict[str, Any]:
        """
        Coordinator retries are important because if planning fails, nothing runs.
        Also: coordinator MUST NOT touch specialist flags.
        """
        policy = retry_policy_for(self.retry_cfg, self.coordinator.agent_id, RetryPolicy(max_attempts=3))
        allow, deny = retry_lists_for(self.retry_cfg, self.coordinator.agent_id)

        return await run_node_with_retry(
            event_bus=self.event_bus,
            agent_id=self.coordinator.agent_id,
            node_fn=self.coordinator.analyze,
            state=state,
            policy=policy,
            validate_update=validate_coordinator_update,
            # Critical: prevent concurrent update collisions
            strip_keys={"bug_agent_completed", "security_agent_completed"},
            is_retryable=lambda e: retry_predicate(e, allow, deny),
            failure_patch={
                "phase": "done",
                "final_report": {"status": "failed", "error": "Coordinator failed"},
            },
        )

    async def _security_node(self, state: ReviewState) -> Dict[str, Any]:
        policy = retry_policy_for(self.retry_cfg, self.security_agent.agent_id, RetryPolicy(max_attempts=2))
        allow, deny = retry_lists_for(self.retry_cfg, self.security_agent.agent_id)

        # Emit plan_step_started
        plan = state.get("plan", {})
        plan_id = plan.get("plan_id", "")
        step_id = self._get_step_id_for_agent(plan, "security")
        if step_id:
            await self.event_bus.publish(create_plan_step_started_event(plan_id, step_id, "security_agent"))

        start_time = time.time()
        result = await run_node_with_retry(
            event_bus=self.event_bus,
            agent_id=self.security_agent.agent_id,
            node_fn=self.security_agent.analyze,
            state=state,
            policy=policy,
            validate_update=validate_security_update,
            # Only security_node can set security flag
            success_patch={"security_agent_completed": True},
            failure_patch={
                "security_agent_completed": True,  # allow join to progress
                "security_findings": [],
                "security_fixes": [],
            },
            # Security must never touch bug flag (this was your concurrency root cause)
            strip_keys={"bug_agent_completed"},
            is_retryable=lambda e: retry_predicate(e, allow, deny),
        )
        
        # Emit plan_step_completed
        if step_id:
            duration_ms = int((time.time() - start_time) * 1000)
            success = result.get("security_agent_completed", False) and len(result.get("security_findings", [])) >= 0
            await self.event_bus.publish(create_plan_step_completed_event(plan_id, step_id, "security_agent", success, duration_ms))
        
        return result

    def _get_step_id_for_agent(self, plan: Dict[str, Any], agent_type: str) -> Optional[str]:
        """Find the step_id for a given agent type in the plan."""
        for step in plan.get("steps", []):
            if step.get("agent") == agent_type:
                return step.get("step_id")
        return None

    async def _bug_node(self, state: ReviewState) -> Dict[str, Any]:
        policy = retry_policy_for(self.retry_cfg, self.bug_agent.agent_id, RetryPolicy(max_attempts=2))
        allow, deny = retry_lists_for(self.retry_cfg, self.bug_agent.agent_id)

        # Emit plan_step_started
        plan = state.get("plan", {})
        plan_id = plan.get("plan_id", "")
        step_id = self._get_step_id_for_agent(plan, "bug")
        if step_id:
            await self.event_bus.publish(create_plan_step_started_event(plan_id, step_id, "bug_agent"))

        start_time = time.time()
        result = await run_node_with_retry(
            event_bus=self.event_bus,
            agent_id=self.bug_agent.agent_id,
            node_fn=self.bug_agent.analyze,
            state=state,
            policy=policy,
            validate_update=validate_bug_update,
            success_patch={"bug_agent_completed": True},
            failure_patch={
                "bug_agent_completed": True,
                "bug_findings": [],
                "bug_fixes": [],
            },
            strip_keys={"security_agent_completed"},
            is_retryable=lambda e: retry_predicate(e, allow, deny),
        )
        
        # Emit plan_step_completed
        if step_id:
            duration_ms = int((time.time() - start_time) * 1000)
            success = result.get("bug_agent_completed", False) and len(result.get("bug_findings", [])) >= 0
            await self.event_bus.publish(create_plan_step_completed_event(plan_id, step_id, "bug_agent", success, duration_ms))
        
        return result






    
    
    