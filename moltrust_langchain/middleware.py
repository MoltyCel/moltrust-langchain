"""MolTrustMiddleware — trust verification for LangChain 1.x agents.

Built against the verified langchain 1.3.11 ``AgentMiddleware`` API
(``langchain.agents.middleware.types``):

    class AgentMiddleware(Generic[StateT, ContextT, ResponseT]):
        def before_model(self, state, runtime) -> dict | None
        def wrap_tool_call(self, request, handler) -> ToolMessage | Command

Usage::

    from langchain.agents import create_agent
    from moltrust_langchain import MolTrustMiddleware

    agent = create_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[...],
        middleware=[MolTrustMiddleware(min_score=60)],
    )
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from ._policy import TrustPolicy
from .exceptions import TrustCheckFailed


class MolTrustMiddleware(AgentMiddleware):
    """Check MolTrust trust scores before model / tool calls.

    Two hook points:

    - ``before_model``: checks *this* agent's own DID (``agent_did``) before it
      reasons. A blocked check **raises** :class:`TrustCheckFailed` (it
      propagates and halts the agent) in ``action="block"``.
    - ``wrap_tool_call``: checks the *target* agent of a tool/A2A call (DID taken
      from the tool-call args under ``did_key``, or ``agent_did_map`` by tool
      name). A blocked call **returns an error** ``ToolMessage`` (so the agent
      can react) rather than raising.

    Args:
        min_score: Minimum acceptable 0-100 MolTrust trust score.
        action: ``"block"`` | ``"warn"`` | ``"log"``.
        agent_did: This agent's MolTrust DID, for the ``before_model`` self-check.
        api_key: Optional MolTrust API key (Tier 2); keyless otherwise.
        client: Preconstructed trust client (for tests / DI).
        agent_did_map: ``{tool_name: did}`` mapping for tool-target resolution.
        did_key: Key to read a DID from tool-call args / runtime context.
        pass_without_did: Allow calls with no resolvable DID (default True).
        check_model / check_tools: Toggle each hook independently.
    """

    def __init__(
        self,
        min_score: float = 60,
        action: str = "block",
        *,
        agent_did: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Any = None,
        agent_did_map: Optional[Dict[str, str]] = None,
        did_key: str = "did",
        pass_without_did: bool = True,
        check_model: bool = True,
        check_tools: bool = True,
    ):
        super().__init__()
        self.policy = TrustPolicy(
            min_score=min_score,
            action=action,
            client=client,
            api_key=api_key,
            pass_without_did=pass_without_did,
        )
        self.agent_did = agent_did
        self.agent_did_map = dict(agent_did_map or {})
        self.did_key = did_key
        self.check_model = check_model
        self.check_tools = check_tools

    # -- hooks -------------------------------------------------------------

    def before_model(self, state, runtime) -> Optional[Dict[str, Any]]:
        if not self.check_model:
            return None
        did = self._resolve_self_did(state, runtime)
        decision = self.policy.evaluate(did)
        if decision.block:
            raise TrustCheckFailed(decision.did or "<none>", decision.score, self.policy.min_score)
        return None  # no state update

    def wrap_tool_call(self, request, handler):
        if not self.check_tools:
            return handler(request)
        did = self._resolve_tool_did(request)
        decision = self.policy.evaluate(did)
        if decision.block:
            tool_call = getattr(request, "tool_call", {}) or {}
            return ToolMessage(
                content=(
                    f"Blocked by MolTrust: target agent {decision.did} failed the trust "
                    f"check ({decision.reason}, min_score={self.policy.min_score})."
                ),
                tool_call_id=tool_call.get("id", ""),
                status="error",
            )
        return handler(request)

    # -- DID resolution ----------------------------------------------------

    def _resolve_self_did(self, state, runtime) -> Optional[str]:
        if self.agent_did:
            return self.agent_did
        ctx = getattr(runtime, "context", None)
        if isinstance(ctx, dict):
            return ctx.get(self.did_key) or ctx.get("moltrust_did")
        if ctx is not None:
            return getattr(ctx, self.did_key, None)
        return None

    def _resolve_tool_did(self, request) -> Optional[str]:
        tool_call = getattr(request, "tool_call", {}) or {}
        args = tool_call.get("args") or {}
        if isinstance(args, dict) and args.get(self.did_key):
            return args[self.did_key]
        name = tool_call.get("name")
        if name in self.agent_did_map:
            return self.agent_did_map[name]
        return None
