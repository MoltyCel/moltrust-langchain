"""Exceptions for moltrust-langchain."""


class MolTrustLangChainError(Exception):
    """Base error for the moltrust-langchain middleware."""


class AgentNotRegistered(MolTrustLangChainError):
    """The DID has no MolTrust registration / trust record (HTTP 404)."""

    def __init__(self, did: str):
        self.did = did
        super().__init__(f"Agent not registered with MolTrust: {did}")


class TrustCheckFailed(MolTrustLangChainError):
    """An agent's trust score is below the configured minimum.

    Raised from ``before_model`` when ``action="block"`` (it propagates and
    halts the agent). In ``wrap_tool_call`` a blocked call instead returns an
    error ``ToolMessage`` rather than raising, so the agent can react.
    """

    def __init__(self, did: str, score, min_score: float):
        self.did = did
        self.score = score
        self.min_score = min_score
        detail = "withheld/none" if score is None else str(score)
        super().__init__(
            f"Trust check failed for {did}: score {detail} < min_score {min_score}"
        )
