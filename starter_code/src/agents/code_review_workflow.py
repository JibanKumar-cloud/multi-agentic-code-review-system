"""
LangGraph-based orchestrator for multi-agent code review.

Simple Architecture:
    coordinator (planning) 
        - ONE Claude call with tools
        - Analyzes code, creates execution plan
        - Emits plan to UI
          ↓
        fanout
        ↙    ↘
  security    bug      ← PARALLEL (each makes Claude call with tools)
        ↘    ↙
         join
          ↓
    coordinator (consolidating)
        - Merges findings from agents
        - Deduplicates
        - Emits final findings + fixes
        - Returns final report
          ↓
         END

Each agent = ONE Claude call with tools + prompt describing what to do.
"""
import logging
import time
import uuid
from typing import Any, Dict

from langgraph.graph import StateGraph, END
from .state import ReviewState

from ..config import config
from ..events import EventBus, create_review_started_event

from . import CoordinatorAgent, SecurityAgent, BugDetectionAgent


logger = logging.getLogger(__name__)



class CodeReviewWorkflow:
    """Simple LangGraph orchestrator - each agent = one Claude call."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # Initialize agents
        self.coordinator = CoordinatorAgent(event_bus)
        self.security_agent = SecurityAgent(event_bus)
        self.bug_agent = BugDetectionAgent(event_bus)

        self.config = config.coordinator_config
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    
    def _build_graph(self) -> StateGraph:
        """
        coordinator → fanout → [security, bug] → join(barrier) → coordinator → END
        """
        graph = StateGraph(ReviewState)

        graph.add_node("coordinator", self.coordinator.analyze)
        graph.add_node("fanout", self._fanout_node)
        graph.add_node("security_agent", self.security_agent.analyze)
        graph.add_node("bug_agent", self.bug_agent.analyze)
        graph.add_node("join", self._join_node)

        graph.set_entry_point("coordinator")

        # coordinator decides whether to fanout (planning) or end (done)
        graph.add_conditional_edges(
            "coordinator",
            self._rout_fanout,
            {"fanout": "fanout", "end": END},
        )

        # TRUE parallel fan-out
        graph.add_edge("fanout", "security_agent")
        graph.add_edge("fanout", "bug_agent")

        # fan-in to join barrier
        graph.add_edge("security_agent", "join")
        graph.add_edge("bug_agent", "join")

        # JOIN BARRIER:
        # keep looping at join until BOTH branches increment completed_agents
        graph.add_conditional_edges(
            "join",
            self._route_join,
            {"end": END, "go": "coordinator"},
        )
        return graph
    
    async def _join_node(self, state: ReviewState) -> Dict[str, Any]:
        # no-op: join condition handled in _route_join
        return {}
    
    async def _fanout_node(self, state: ReviewState):
        return {}
    
    def _rout_fanout(self, state: ReviewState) -> str:
            # planning -> run specialists, consolidating/done -> end
        return "fanout" if state.get("phase") == "planning" else "end"

    def _route_join(self, state: ReviewState) -> str:
        # wait until both branches report completion
        bug_done = state.get("bug_agent_completed", False)
        sec_done = state.get("security_agent_completed", False)
        return "go" if (bug_done and sec_done) else "end"
    
    async def review_code(self, code: str, filename: str = "code.py") -> Dict[str, Any]:
        review_id = str(uuid.uuid4())[:8]
        
        await self.event_bus.publish(create_review_started_event(
            review_id, filename, len(code.split('\n'))
        ))
        
        initial_state: ReviewState = {
            "code": code,
            "filename": filename,
            "review_id": review_id,
            "phase": "",
            "plan": {},
            "security_findings": [],
            "security_fixes": [],
            "bug_findings": [],
            "bug_fixes": [],
            "final_findings": [],
            "final_fixes": [],
            "final_report": None,
            "start_time": time.time(),
            "errors": [],
            "bug_agent_completed": False,
            "security_agent_completed": False,
            "agent_run_mode": "parallel",
            "step_ids": set()
        }
        
        try:
            final_state = await self._run_graph(initial_state)
            return final_state.get("final_report", {})
        except Exception as e:
            logger.error(f"Review failed: {e}")
            return {"error": str(e)}
    
    async def _run_graph(self, state: ReviewState) -> ReviewState:
        """Execute graph - try native, fallback to manual."""
        try:
            return await self.app.ainvoke(state)
        except Exception as e:
            logger.warning(f"LangGraph ainvoke failed: {e}, using manual")
    

    
    