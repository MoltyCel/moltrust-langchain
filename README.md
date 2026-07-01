# moltrust-langchain

**Add trust verification to LangChain 1.x agents in one line.**

`moltrust-langchain` plugs into LangChain 1.x's `AgentMiddleware` hook system to
check **MolTrust trust scores** before an agent reasons and before it calls out
to other agents/tools. Below-threshold agents are blocked (or warned/logged).

## Install

```bash
pip install moltrust-langchain
```

## Usage

```python
from langchain.agents import create_agent
from moltrust_langchain import MolTrustMiddleware

agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[...],
    middleware=[MolTrustMiddleware(min_score=60)],
)
```

> This example matches the real `langchain.agents.create_agent` signature
> (`middleware: Sequence[AgentMiddleware] = ()`), verified against
> **langchain 1.3.11**.

## Usage tiers

**Tier 1 — no account required (default):**

```python
MolTrustMiddleware(min_score=60)          # keyless; reads scores rate-limited
```

**Tier 2 — free account (higher limits):**

```python
MolTrustMiddleware(min_score=60, api_key="mt_...")   # or MOLTRUST_API_KEY env
```

The API key is sent as the `X-API-Key` header only when present.

## What it does

`MolTrustMiddleware` is a `langchain.agents.middleware.AgentMiddleware`. It uses
two hook points (verified against langchain 1.3.11):

- **`before_model(state, runtime)`** — checks *this* agent's own DID
  (`agent_did=...`) before it reasons. A blocked check **raises**
  `TrustCheckFailed` (halts the agent) when `action="block"`.
- **`wrap_tool_call(request, handler)`** — checks the *target* of a tool / A2A
  call (DID from the tool-call args under `did_key`, or `agent_did_map` by tool
  name). A blocked call **returns an error `ToolMessage`** (the agent can react)
  instead of raising.

`min_score` is on the **0–100 MolTrust trust score** (`trust_score` from
`GET /skill/trust-score/{did}`) — the behavioral score, not a 0–5 rating.
Scores are **recomputable**: verify the on-chain solvency component of any agent
yourself at

```
https://api.moltrust.ch/credits/solvency/{did}
```

### Options

```python
MolTrustMiddleware(
    min_score=60,               # 0-100 trust score threshold
    action="block",             # "block" | "warn" | "log"
    agent_did="did:moltrust:…",  # this agent's DID (before_model self-check)
    agent_did_map={"call_agent": "did:moltrust:…"},  # tool → target DID
    did_key="did",              # DID key in tool-call args / runtime context
    pass_without_did=True,       # allow calls with no resolvable DID
    check_model=True, check_tools=True,
)
```

## Difference from Microsoft AGT

[Microsoft's Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
enforces **policies** — *what an agent may do* (scope, sandboxing, zero-trust
identity). MolTrust verifies **behavioral trust** — *is this agent trustworthy,
based on verifiable history*. **Complementary, not competing**: AGT bounds
authority; MolTrust decides who has earned it.

## Honest limitations (0.1.0)

- LangChain agents have no MolTrust DID by default — supply `agent_did` (for the
  self-check) and/or a `did` in tool-call args or `agent_did_map` (for targets).
- A **withheld** score (registered agent, too few endorsements → API returns
  `trust_score: null`) is treated like an unregistered agent: fail-closed in
  `block`, fail-open in `warn`/`log`.
- On a registry/transport error the middleware **fails open** (logs, allows) so a
  MolTrust hiccup never breaks your agent.
- Synchronous hooks only. For fully async agents (`ainvoke`/`astream`), async
  `abefore_model`/`awrap_tool_call` are a follow-up.

## License

MIT © CryptoKRI GmbH — see [LICENSE](LICENSE).
