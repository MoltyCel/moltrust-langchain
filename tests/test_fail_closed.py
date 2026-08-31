"""M7 — lookup errors deny by default; opt-out and cache are the release valves."""
import pytest

from moltrust_langchain._policy import TrustPolicy
from moltrust_langchain.exceptions import AgentNotRegistered, MolTrustLangChainError

DID = "did:moltrust:aaaabbbbccccdddd"


class _Client:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def get_trust_score(self, did):
        self.calls += 1
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


def _policy(behaviour, **kw):
    return TrustPolicy(client=_Client(behaviour), **kw)


def test_lookup_error_now_blocks(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    d = _policy(MolTrustLangChainError("down")).evaluate(DID)
    assert d.block is True
    assert d.reason == "lookup_error_failclosed"


def test_opt_out_restores_the_old_behaviour(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    d = _policy(MolTrustLangChainError("down"), fail_open=True).evaluate(DID)
    assert d.block is False
    assert d.reason == "lookup_error_failopen"


def test_env_var_opts_out(monkeypatch):
    monkeypatch.setenv("MOLTRUST_FAIL_OPEN", "true")
    d = _policy(MolTrustLangChainError("down")).evaluate(DID)
    assert d.block is False


def test_a_brief_outage_rides_on_the_cached_score(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    p = _policy(MolTrustLangChainError("down"), cache_ttl=0, cache_stale_grace=300)
    p._cache.put(DID, 90.0)
    d = p.evaluate(DID)
    assert d.block is False
    assert d.reason == "ok_cached_stale"


def test_a_stale_score_is_still_measured(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    p = _policy(MolTrustLangChainError("down"), min_score=60, cache_ttl=0, cache_stale_grace=300)
    p._cache.put(DID, 10.0)
    d = p.evaluate(DID)
    assert d.block is True


def test_a_fresh_entry_skips_the_lookup():
    client = _Client(90.0)
    p = TrustPolicy(client=client, cache_ttl=60)
    p._cache.put(DID, 90.0)
    p.evaluate(DID)
    assert client.calls == 0


def test_unregistered_still_blocks():
    d = _policy(AgentNotRegistered(DID), fail_open=True).evaluate(DID)
    assert d.block is True
