from __future__ import annotations

import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Set, Dict, Any
from ..events import EventBus
from .retry_errors import AgentMissingFieldsError
from .utility import emit_agent_completed
from ..events.event_types import create_agent_error_event
from typing import Any, Awaitable, Callable, Dict, Optional, Set, List

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    base_delay_s: float = 0.4
    max_delay_s: float = 3.0
    jitter_s: float = 0.15  # small jitter to avoid thundering herd


def _backoff_delay(policy: RetryPolicy, attempt: int) -> float:
    delay = policy.base_delay_s * (2 ** (attempt - 1))
    delay = min(delay, policy.max_delay_s)
    delay = delay + (policy.jitter_s * (0.5 - (time.time() % 1)))
    return max(0.0, delay)


def is_retryable_by_config(err: Exception, allowlist: Set[str], denylist: Set[str]) -> bool:
    name = err.__class__.__name__
    if name in denylist:
        return False
    if allowlist and name in allowlist:
        return True
    return False

def validate_security_update(update: Dict[str, Any]) -> None:
    """
    Ensures security node produced structurally usable output
    (you can tighten/relax this contract as needed).
    """
    if "security_findings" not in update or "security_fixes" not in update:
        raise AgentMissingFieldsError("Missing security_findings/security_fixes")
    if not isinstance(update["security_findings"], list) or not isinstance(update["security_fixes"], list):
        raise AgentMissingFieldsError("security_findings/security_fixes must be lists")


def validate_bug_update(update: Dict[str, Any]) -> None:
    if "bug_findings" not in update or "bug_fixes" not in update:
        raise AgentMissingFieldsError("Missing bug_findings/bug_fixes")
    if not isinstance(update["bug_findings"], list) or not isinstance(update["bug_fixes"], list):
        raise AgentMissingFieldsError("bug_findings/bug_fixes must be lists")


def validate_coordinator_update(update: Dict[str, Any]) -> None:
    """
    Coordinator planning phase must produce a plan with steps.
    Coordinator consolidating phase typically produces final_report.
    Keep it tolerant but not silent.
    """
    # If coordinator says planning, require plan
    phase = update.get("phase")
    if phase == "planning":
        plan = update.get("plan", {})
        if not isinstance(plan, dict) or not plan.get("steps"):
            raise AgentMissingFieldsError("Coordinator planning produced no plan steps")
    # If coordinator says done, it should produce final_report
    if phase == "done" and "final_report" not in update:
        raise AgentMissingFieldsError("Coordinator done produced no final_report")
    

async def run_node_with_retry(
    *,
    event_bus: EventBus,
    agent_id: str,
    node_fn: Callable[[Any], Awaitable[Dict[str, Any]]],
    state: Any,
    policy: RetryPolicy,
    validate_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    success_patch: Optional[Dict[str, Any]] = None,
    failure_patch: Optional[Dict[str, Any]] = None,
    strip_keys: Optional[Set[str]] = None,
    is_retryable: Optional[Callable[[Exception], bool]] = None,
) -> Dict[str, Any]:
    success_patch = success_patch or {}
    failure_patch = failure_patch or {}
    strip_keys = strip_keys or set()

    last_err: Optional[Exception] = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            update = await node_fn(state)

            if not isinstance(update, dict):
                raise TypeError(f"{agent_id} node must return dict, got {type(update)}")

            # Defensive: strip forbidden keys
            for k in strip_keys:
                update.pop(k, None)

            # Validate shape (raise => retryable structural failure)
            if validate_update is not None:
                validate_update(update)

            # Ensure success patch applied last
            update.update(success_patch)
            return update

        except Exception as e:
            last_err = e
            retryable = True if is_retryable is None else bool(is_retryable(e))

            # Emit “error + will_retry” to UI
            will_retry = retryable and (attempt < policy.max_attempts)
            last_err = e

            if (attempt >= policy.max_attempts) or (not retryable):
                logger.error(f"[{agent_id}] failed: {e}", exc_info=True)
                out = dict(failure_patch)
                out.setdefault("errors", [])
                out["errors"].append({"agent": agent_id, "error": str(e), "attempts": attempt})
                return out

            delay = _backoff_delay(policy, attempt)
            await event_bus.publish(
                    create_agent_error_event(
                        agent_id=agent_id,
                        error_type="node_error",
                        message=str(e),
                        recoverable=retryable,
                        will_retry=will_retry,
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_s = delay if will_retry else 0))
            logger.warning(f"[{agent_id}] retry {attempt}/{policy.max_attempts} in {delay:.2f}s: {e}")
            await asyncio.sleep(delay)

    # should never happen
    return dict(failure_patch, errors=[{"agent": agent_id, "error": str(last_err)}])

def retry_predicate(err: Exception, allow: Set[str], deny: Set[str]) -> bool:
    """
    Best practice:
    - NEVER retry deterministic “invalid request” issues
    - DO retry transient + output-structure issues (invalid JSON/empty/missing keys)
    - Allowlist is config-driven
    """
    # Always retry our structural output errors (unless explicitly denied)
    if err.__class__.__name__ in {"AgentEmptyResponseError", "AgentInvalidJSONError", "AgentMissingFieldsError"}:
        return err.__class__.__name__ not in deny

    # If anthropic/openai SDK error objects expose status codes, block 400-type
    msg = str(err).lower()
    if "invalid_request" in msg or "error code: 400" in msg or "input should be a valid list" in msg:
        return False

    # config allow/deny
    return is_retryable_by_config(err, allow, deny)


def retry_policy_for(retry_cfg: Dict[str, Any], agent_id: str, default: RetryPolicy) -> RetryPolicy:
    node_cfg = (retry_cfg.get(agent_id) or {})
    return RetryPolicy(
        max_attempts=int(node_cfg.get("max_attempts", default.max_attempts)),
        base_delay_s=float(node_cfg.get("base_delay_s", default.base_delay_s)),
        max_delay_s=float(node_cfg.get("max_delay_s", default.max_delay_s)),
        jitter_s=float(node_cfg.get("jitter_s", default.jitter_s)),
    )

def retry_lists_for(retry_cfg: Dict[str, Any], agent_id: str) -> tuple[Set[str], Set[str]]:
    node_cfg = (retry_cfg.get(agent_id) or {})
    allow = set(node_cfg.get("retry_exceptions", []) or [])
    deny = set(node_cfg.get("never_retry_exceptions", []) or [])
    return allow, deny
