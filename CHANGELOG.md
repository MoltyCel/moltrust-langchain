# Changelog

All notable changes to `moltrust-langchain` are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [0.1.2] — 2026-07-01

### Added
- Branded `User-Agent` header (`moltrust-langchain/<version>`) on every trust-score
  request, so MolTrust can attribute API traffic to the framework
  integration. Sent in both keyless (Tier 1) and keyed (Tier 2) modes.

## [0.1.1] — 2026-07-01

### Fixed
- Classic license metadata for PyPI compatibility: `license = { text = "MIT" }`
  emits `License: MIT` instead of `License-Expression: MIT`.
- Suppress hatchling's `License-File` metadata generation via `license-files = []`
  (PEP 639) — verified: built METADATA no longer carries a `License-File` entry.

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
