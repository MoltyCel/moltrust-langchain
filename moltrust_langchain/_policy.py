"""Trust-decision logic — deliberately free of any langchain import.

Keeping the policy here (rather than inside ``middleware.py``) means it is
fully unit-testable with a mocked client and no langchain installed. The
``MolTrustMiddleware`` adapter in ``middleware.py`` just wires langchain's
``state`` / ``ToolCallRequest`` into ``TrustPolicy.evaluate(did)``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from ._trust_cache import TrustScoreCache
from .client import TrustClient
from .exceptions import AgentNotRegistered, MolTrustLangChainError

logger = logging.getLogger("moltrust_langchain")

VALID_ACTIONS = ("block", "warn", "log")


@dataclass
class Decision:
    """Result of a trust evaluation.

    ``block`` is True only when a deny condition is met AND ``action == "block"``
    (in ``warn``/``log`` the condition is logged but the call is allowed).
    """

    block: bool
    score: Optional[float]
    reason: str
    did: Optional[str]


class TrustPolicy:
    def __init__(
        self,
        min_score: float = 60,
        action: str = "block",
        *,
        client: Optional[TrustClient] = None,
        api_key: Optional[str] = None,
        pass_without_did: bool = True,
        fail_open: Optional[bool] = None,
        cache_ttl: float = 60.0,
        cache_stale_grace: float = 300.0,
    ):
        if action not in VALID_ACTIONS:
            raise ValueError(f"action must be one of {VALID_ACTIONS}, got {action!r}")
        self.min_score = min_score
        self.action = action
        self.pass_without_did = pass_without_did
        if fail_open is None:
            fail_open = os.getenv("MOLTRUST_FAIL_OPEN", "").strip().lower() in {"1", "true", "yes"}
        self.fail_open = fail_open
        self._cache = TrustScoreCache(ttl=cache_ttl, stale_grace=cache_stale_grace)
        self._client = client
        self._api_key = api_key

    def _get_client(self) -> TrustClient:
        if self._client is None:
            self._client = TrustClient(api_key=self._api_key)
        return self._client

    def evaluate(self, did: Optional[str]) -> Decision:
        """Evaluate a DID and return a :class:`Decision`."""
        if not did:
            if self.pass_without_did:
                return Decision(False, None, "no_did_allowed", None)
            return self._deny(None, None, "no_did")

        hit, cached = self._cache.get_fresh(did)
        if hit:
            return self._from_score(did, cached, "cached")

        try:
            score = self._get_client().get_trust_score(did)
        except AgentNotRegistered:
            return self._deny(did, None, "unregistered")
        except MolTrustLangChainError as exc:
            hit, cached = self._cache.get_stale(did)
            if hit:
                logger.warning(
                    "MolTrust: lookup failed for %s (%s); using cached score", did, exc
                )
                return self._from_score(did, cached, "cached_stale")
            if self.fail_open:
                logger.warning(
                    "MolTrust: lookup failed for %s (%s); allowing (fail_open)", did, exc
                )
                return Decision(False, None, "lookup_error_failopen", did)
            logger.warning(
                "MolTrust: lookup failed for %s (%s); blocking (fail_closed)", did, exc
            )
            return Decision(True, None, "lookup_error_failclosed", did)

        self._cache.put(did, score)

        if score is None:
            return self._deny(did, None, "withheld")
        if score < self.min_score:
            return self._deny(did, score, "low_score")
        return Decision(False, score, "ok", did)

    def _deny(self, did: Optional[str], score: Optional[float], reason: str) -> Decision:
        if self.action == "block":
            logger.warning("MolTrust BLOCK did=%s (%s, score=%s)", did, reason, score)
            return Decision(True, score, reason, did)
        if self.action == "warn":
            logger.warning("MolTrust WARN did=%s (%s, score=%s)", did, reason, score)
        else:  # "log"
            logger.info("MolTrust LOG did=%s (%s, score=%s)", did, reason, score)
        return Decision(False, score, reason, did)

    def _from_score(self, did: str, score, suffix: str) -> "Decision":
        """Build a Decision from a cached score."""
        if score is None:
            return self._deny(did, None, f"withheld_{suffix}")
        if score < self.min_score:
            return self._deny(did, score, f"low_score_{suffix}")
        return Decision(False, score, f"ok_{suffix}", did)
