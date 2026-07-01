"""moltrust-langchain — trust verification middleware for LangChain 1.x.

    from langchain.agents import create_agent
    from moltrust_langchain import MolTrustMiddleware

    agent = create_agent(model="...", tools=[...],
                         middleware=[MolTrustMiddleware(min_score=60)])

``MolTrustMiddleware`` is imported lazily so this package (and its trust-policy
logic / HTTP client) can be imported and unit-tested without langchain present.
"""

from .exceptions import (
    MolTrustLangChainError,
    AgentNotRegistered,
    TrustCheckFailed,
)

__version__ = "0.1.0"
__all__ = [
    "MolTrustMiddleware",
    "MolTrustLangChainError",
    "AgentNotRegistered",
    "TrustCheckFailed",
    "__version__",
]


def __getattr__(name: str):  # PEP 562 — lazy import of the langchain adapter
    if name == "MolTrustMiddleware":
        from .middleware import MolTrustMiddleware

        return MolTrustMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
