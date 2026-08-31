"""Mock-based tests. No real API calls.

The trust-decision logic (``TrustPolicy``) and the HTTP client (``TrustClient``)
are langchain-free and fully tested here. The ``MolTrustMiddleware`` adapter is
tested behind ``importorskip("langchain")`` — it runs wherever langchain is
installed (CI / user machines); it is skipped in a langchain-less build env.
"""

import pytest

from moltrust_langchain._policy import TrustPolicy, Decision
from moltrust_langchain.client import TrustClient
from moltrust_langchain.exceptions import (
    AgentNotRegistered,
    MolTrustLangChainError,
    TrustCheckFailed,
)

DID = "did:moltrust:0123456789abcdef"


class FakeClient:
    def __init__(self, score=None, raises=None):
        self._score = score
        self._raises = raises

    def get_trust_score(self, did):
        if self._raises is not None:
            raise self._raises
        return self._score


def _policy(score=None, raises=None, **kw):
    return TrustPolicy(client=FakeClient(score=score, raises=raises), **kw)


# -- TrustPolicy: block mode ----------------------------------------------

def test_low_score_blocks():
    assert _policy(score=42, min_score=60, action="block").evaluate(DID).block is True


def test_high_score_allows():
    d = _policy(score=88, min_score=60, action="block").evaluate(DID)
    assert d.block is False and d.score == 88


def test_score_equal_min_allows():
    assert _policy(score=60, min_score=60, action="block").evaluate(DID).block is False


def test_withheld_blocks_in_block_mode():
    d = _policy(score=None, min_score=60, action="block").evaluate(DID)
    assert d.block is True and d.reason == "withheld"


def test_unregistered_blocks_in_block_mode():
    d = _policy(raises=AgentNotRegistered(DID), min_score=60, action="block").evaluate(DID)
    assert d.block is True and d.reason == "unregistered"


def test_transport_error_fails_closed():
    """0.2.0 (M7): a registry error denies unless the integration opts out."""
    d = _policy(raises=MolTrustLangChainError("boom"), min_score=60, action="block").evaluate(DID)
    assert d.block is True and d.reason == "lookup_error_failclosed"


def test_transport_error_fails_open_when_opted_out():
    d = _policy(
        raises=MolTrustLangChainError("boom"), min_score=60, action="block", fail_open=True
    ).evaluate(DID)
    assert d.block is False and d.reason == "lookup_error_failopen"


# -- TrustPolicy: no DID / warn / log -------------------------------------

def test_no_did_passes_by_default():
    assert _policy(score=0, min_score=60).evaluate(None).block is False


def test_no_did_blocked_when_pass_without_did_false():
    d = _policy(score=0, min_score=60, action="block", pass_without_did=False).evaluate(None)
    assert d.block is True and d.reason == "no_did"


def test_warn_mode_allows():
    assert _policy(score=5, min_score=60, action="warn").evaluate(DID).block is False


def test_log_mode_allows():
    assert _policy(score=5, min_score=60, action="log").evaluate(DID).block is False


def test_invalid_action_rejected():
    with pytest.raises(ValueError):
        TrustPolicy(action="nope")


# -- TrustClient HTTP (mocked /skill/trust-score, keyless + keyed) ---------

from unittest import mock  # noqa: E402
import requests as _requests  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_keyless_sends_no_api_key(mget, monkeypatch):
    monkeypatch.delenv("MOLTRUST_API_KEY", raising=False)
    mget.return_value = FakeResponse(200, {"trust_score": 70, "withheld": False})
    assert TrustClient().get_trust_score(DID) == 70.0
    args, kwargs = mget.call_args
    assert args[0].endswith(f"/skill/trust-score/{DID}")
    assert "X-API-Key" not in kwargs["headers"]  # Tier-1 keyless


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_with_key_sends_header(mget):
    mget.return_value = FakeResponse(200, {"trust_score": 70, "withheld": False})
    TrustClient(api_key="mt_test").get_trust_score(DID)
    assert mget.call_args.kwargs["headers"]["X-API-Key"] == "mt_test"


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_withheld_returns_none(mget):
    mget.return_value = FakeResponse(200, {"trust_score": None, "withheld": True})
    assert TrustClient(api_key="k").get_trust_score(DID) is None


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_404_raises_not_registered(mget):
    mget.return_value = FakeResponse(404, {})
    with pytest.raises(AgentNotRegistered):
        TrustClient(api_key="k").get_trust_score(DID)


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_http_error_raises(mget):
    mget.return_value = FakeResponse(500, {})
    with pytest.raises(MolTrustLangChainError):
        TrustClient(api_key="k").get_trust_score(DID)


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_network_error_raises(mget):
    mget.side_effect = _requests.RequestException("boom")
    with pytest.raises(MolTrustLangChainError):
        TrustClient(api_key="k").get_trust_score(DID)


# -- MolTrustMiddleware adapter (requires langchain) ----------------------

def test_middleware_before_model_blocks_by_raising():
    pytest.importorskip("langchain.agents.middleware")
    from moltrust_langchain import MolTrustMiddleware

    mw = MolTrustMiddleware(min_score=60, action="block", agent_did=DID,
                            client=FakeClient(score=10))

    class _RT:
        context = None

    with pytest.raises(TrustCheckFailed):
        mw.before_model({"messages": []}, _RT())


def test_middleware_wrap_tool_call_blocks_with_toolmessage():
    pytest.importorskip("langchain.agents.middleware")
    from langchain_core.messages import ToolMessage
    from moltrust_langchain import MolTrustMiddleware

    mw = MolTrustMiddleware(min_score=60, action="block",
                            client=FakeClient(score=10), did_key="did")

    class _Req:
        tool_call = {"id": "call_1", "name": "call_agent", "args": {"did": DID}}

    called = {"handler": False}

    def handler(_req):
        called["handler"] = True
        return "should-not-run"

    result = mw.wrap_tool_call(_Req(), handler)
    assert isinstance(result, ToolMessage) and result.status == "error"
    assert called["handler"] is False  # handler never invoked → blocked


# -- branded User-Agent header (0.1.2) ------------------------------------

@mock.patch("moltrust_langchain.client.requests.get")
def test_client_sends_branded_user_agent_keyless(mget, monkeypatch):
    monkeypatch.delenv("MOLTRUST_API_KEY", raising=False)
    mget.return_value = FakeResponse(200, {"trust_score": 70, "withheld": False})
    TrustClient().get_trust_score(DID)
    from moltrust_langchain import __version__
    assert mget.call_args.kwargs["headers"]["User-Agent"] == f"moltrust-langchain/{__version__}"


@mock.patch("moltrust_langchain.client.requests.get")
def test_client_sends_branded_user_agent_with_key(mget):
    mget.return_value = FakeResponse(200, {"trust_score": 70, "withheld": False})
    TrustClient(api_key="mt_test").get_trust_score(DID)
    from moltrust_langchain import __version__
    h = mget.call_args.kwargs["headers"]
    assert h["User-Agent"] == f"moltrust-langchain/{__version__}"
    assert h["X-API-Key"] == "mt_test"
