# Changelog

All notable changes to `moltrust-langchain` are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-01

Initial release. Skeleton + working code (not published to PyPI).

### Added
- `MolTrustMiddleware` — a `langchain.agents.middleware.AgentMiddleware`
  (verified against **langchain 1.3.11**):
  - `before_model(state, runtime)` — self-check on `agent_did`; blocks by
    raising `TrustCheckFailed` in `action="block"`.
  - `wrap_tool_call(request, handler)` — target-agent check; blocks by returning
    an error `ToolMessage` (handler not invoked).
  - `action` modes: `block` | `warn` | `log`; DID resolution via `agent_did`,
    `agent_did_map`, or `tool_call.args[did_key]`.
- `TrustPolicy` — langchain-free trust-decision logic (fully unit-testable).
- `TrustClient` — keyless-by-default HTTP client for
  `GET /skill/trust-score/{did}` (0–100 `trust_score`; `None` when withheld).
  Tier-2 `X-API-Key` sent only when a key is provided.
- Exceptions: `MolTrustLangChainError`, `AgentNotRegistered`, `TrustCheckFailed`.
- Mock-based tests (no live API). Middleware-adapter tests gated on langchain
  being installed.
