# System Analysis: Zabbix MCP Server

**Date:** 2026-04-17
**Input document:** `/Users/bereznevn/Documents/ProjectRepos/agentic-session/business-analysis.md`
**Author:** Python System Analyst

---

## 1. Functional Requirements

| ID   | Requirement | Priority (MoSCoW) | Source (ref to business need) |
|------|-------------|-------------------|-------------------------------|
| F-01 | The system SHALL return a list of active problems filtered by host, host group, and/or severity level | Must | BA §6.1 F-01; US-02 — daily use case for every engineer |
| F-02 | The system SHALL acknowledge a problem by ID, recording a mandatory human-readable comment | Must | BA §6.1 F-02; US-03 — eliminates UI dependency during incidents |
| F-03 | The system SHALL create a maintenance period for specified hosts or host groups with configurable duration and reason | Must | BA §6.1 F-03; US-04 — 8-click UI flow reduced to one call |
| F-04 | The system SHALL add a new host with name, IP address, assigned templates, and host groups in a single operation | Must | BA §6.1 F-04; US-01 — 20-min onboarding reduced to 1 min |
| F-05 | The system SHALL return the current value of a Zabbix item identified by item key and host name/ID | Must | BA §6.1 F-05; US-05 — eliminates 3-request manual API sequence |
| F-06 | The system SHALL return the metric value history for a host/item pair within a caller-specified time range | Must | BA §6.1 F-06; US-05 — required for incident analysis and trend reporting |
| F-07 | The system SHALL search for hosts matching any combination of name substring, host group, linked template, and tag | Must | BA §6.1 F-07; US-09 — critical for navigation in 1 000+ host installations |
| F-08 | The system SHALL return the list of triggers configured for a host, including their current state and expression | Should | BA §6.1 F-08 — diagnostic context for monitoring configuration review |
| F-09 | The system SHALL create or update a trigger with syntax validation of the trigger expression before committing | Should | BA §6.1 F-09; US-07 — reduces misconfiguration errors |
| F-10 | The system SHALL return an incident summary for a given problem or time window: affected hosts, triggered items, and event timeline | Should | BA §6.1 F-10; US-06 — reduces incident context gathering from 20 min to 2 min |
| F-11 | The system SHALL update a named macro value across all hosts matching a name pattern or tag | Should | BA §6.1 F-11; US-10 — bulk macro change without per-host manual edits |
| F-12 | The system SHALL generate an availability report for a list of hosts over a specified calendar period | Should | BA §6.1 F-12; US-08 — replaces 2–4 h of manual SLA report assembly |
| F-13 | The system SHALL search for items (metrics) across hosts by name, key substring, or description | Could | BA §6.1 F-13 — removes dependency on exact item key knowledge |
| F-14 | The system SHALL check and return the availability status of the Zabbix agent on a specified host | Could | BA §6.1 F-14 — quick agent diagnostic without UI navigation |
| F-15 | The system SHALL export metric data for specified hosts and items over a period in JSON or CSV format | Could | BA §6.1 F-15 — external system integration and ad-hoc data analysis |

---

## 2. Non-Functional Requirements

| ID    | Category        | Requirement | Acceptance Criteria |
|-------|-----------------|-------------|---------------------|
| NF-01 | Security        | The system SHALL read Zabbix API credentials exclusively from environment variables (`ZABBIX_URL`, `ZABBIX_API_TOKEN`); credentials must never be written to disk or appear in logs | Automated test confirms no credential substring appears in log output; static analysis (bandit) reports 0 secrets-in-code findings |
| NF-02 | Performance     | Standard tool calls returning ≤100 objects SHALL complete within 5 s wall-clock time under normal Zabbix API conditions; calls returning >100 objects MUST use server-side pagination | p95 response time ≤5 s measured in integration tests against a live Zabbix 6.0 sandbox; pagination verified by unit test with mocked responses |
| NF-03 | Compatibility   | The system SHALL operate correctly against Zabbix API versions 6.0 LTS, 6.4, and 7.0 | CI matrix runs integration smoke tests against Docker images of all three versions; no version-specific failures |
| NF-04 | Reliability     | The system SHALL return a structured, human-readable error message for every Zabbix API error, network timeout, or invalid parameter, without propagating raw JSON error payloads to the LLM | Unit tests cover all documented Zabbix error codes (AUTH_FAILED, OBJECT_NOT_FOUND, etc.) and assert human-readable output format |
| NF-05 | Idempotency     | Create operations (add_host, create_maintenance) SHALL detect pre-existing objects by unique key and return the existing object ID without raising an error | Idempotency verified by calling each create tool twice in succession in integration tests; second call returns the same ID and no error |
| NF-06 | Observability   | Every tool invocation SHALL emit a structured log entry (JSON) containing: timestamp, tool name, sanitized input parameters, duration_ms, and outcome (success/error) | Log entries validated against a JSON schema in unit tests; sensitive fields (token) absent from log output |
| NF-07 | Configurability | Zabbix API URL, API token, HTTP timeout, and pagination limit SHALL be configurable exclusively via environment variables with documented defaults | `ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_TIMEOUT_SECONDS` (default 10), `ZABBIX_PAGE_LIMIT` (default 100); integration test verifies overrides are respected |
| NF-08 | Maintainability | Code coverage for unit + integration tests SHALL be ≥80 %; all public interfaces SHALL be type-annotated and validated with `mypy --strict` | CI gate: `pytest --cov` reports ≥80 %; `mypy --strict` exits with code 0 |

---

## 3. Solution Architecture

### 3.1. High-Level Architecture

The server is structured as a three-layer Python process communicating with an LLM host via the MCP protocol over **stdio** transport (default) or **SSE** transport (optional, for remote deployment).

```
┌───────────────────────────────────────────────┐
│                  LLM Host (Claude, GPT, etc.)  │
│           MCP Client (via stdio / SSE)         │
└─────────────────────┬─────────────────────────┘
                      │ MCP Protocol (JSON-RPC 2.0)
┌─────────────────────▼─────────────────────────┐
│              MCP Transport Layer               │
│         (stdio handler / SSE endpoint)         │
├───────────────────────────────────────────────┤
│              Tools Layer                       │
│  (12 MCP tool definitions + input validation)  │
│  get_active_problems │ acknowledge_problem      │
│  create_maintenance  │ add_host                 │
│  get_metric_value    │ get_metric_history       │
│  search_hosts        │ get_incident_summary     │
│  create_trigger      │ get_availability_report  │
│  bulk_update_macro   │ search_items             │
├───────────────────────────────────────────────┤
│              Zabbix API Client Layer           │
│  Async HTTP client, auth management,           │
│  pagination, error mapping, retry logic        │
├───────────────────────────────────────────────┤
│              Configuration Layer               │
│  Env-var loading, defaults, validation         │
└───────────────────────────────────────────────┘
                      │ HTTPS / JSON-RPC
┌─────────────────────▼─────────────────────────┐
│              Zabbix API (6.0 / 6.4 / 7.0)     │
└───────────────────────────────────────────────┘
```

### 3.2. Component Breakdown

| Component | Responsibility | Technology | Notes |
|-----------|---------------|------------|-------|
| `server.py` | MCP server entry point; registers all tools; starts transport | `mcp` SDK | Single `@mcp.tool` decorator per tool; async handlers |
| `config.py` | Loads and validates all environment variables; provides a singleton `Settings` object | `pydantic-settings` v2 | Fails fast at startup if required vars are missing |
| `tools/problems.py` | Handlers for `get_active_problems`, `acknowledge_problem`, `get_incident_summary` | Python + pydantic | Maps raw Zabbix problem/event objects to clean response models |
| `tools/hosts.py` | Handlers for `add_host`, `search_hosts`, `check_host_availability`, `bulk_update_macro` | Python + pydantic | Implements idempotency check for `add_host` |
| `tools/metrics.py` | Handlers for `get_metric_value`, `get_metric_history`, `search_items`, `export_metrics` | Python + pydantic | Handles pagination for history queries |
| `tools/maintenance.py` | Handler for `create_maintenance` | Python + pydantic | Idempotency: deduplicates by name + time window |
| `tools/triggers.py` | Handlers for `create_trigger`, `get_triggers` | Python + pydantic | Pre-validates expression syntax via Zabbix `apiinfo`/test endpoint |
| `tools/reports.py` | Handler for `get_availability_report` | Python + pydantic | Aggregates SLA from `trend.get` / `history.get` |
| `zabbix/client.py` | Async JSON-RPC client for Zabbix API; manages auth token lifecycle, retries, pagination, error mapping | `httpx` (AsyncClient) | Single re-usable client instance per server process |
| `zabbix/models.py` | Pydantic v2 models for Zabbix API request/response DTOs | `pydantic` v2 | Version-conditioned field aliases handle 6.0 vs 7.0 API differences |
| `zabbix/errors.py` | Maps Zabbix JSON-RPC error codes to human-readable `ZabbixError` exceptions | Python | Referenced by all tool handlers |

### 3.3. Data Flow

**Typical read flow (`get_active_problems`):**
1. LLM host calls the MCP tool with JSON-encoded arguments over stdio.
2. `server.py` deserializes arguments; pydantic validates them.
3. Tool handler calls `ZabbixClient.problem_get(...)`.
4. `ZabbixClient` issues `problem.get` JSON-RPC over HTTPS; handles pagination if result count equals `ZABBIX_PAGE_LIMIT`.
5. Raw Zabbix response is deserialized into pydantic `Problem` models.
6. Tool handler maps models to a human-readable `list[ProblemResult]` response.
7. Response is serialized to JSON and returned to the LLM host via MCP.
8. `structlog` emits a JSON log entry with duration and outcome.

**Typical write flow (`acknowledge_problem`):**
1–2. Same as above.
3. Tool handler calls `ZabbixClient.event_acknowledge(event_ids, message, action)`.
4. If Zabbix returns an error code, `ZabbixClient` raises a `ZabbixError` with a human-readable message.
5. Tool handler returns either a success confirmation or the human-readable error string.
6. Structured log entry is emitted.

**Create with idempotency (`add_host`):**
1–2. Same as above.
3. Tool handler calls `ZabbixClient.host_get(filter={"host": name})`.
4. If host already exists, returns existing `hostid` immediately.
5. Otherwise calls `ZabbixClient.host_create(...)`.
6. Returns new `hostid` and confirmation message.

### 3.4. Integration Points

| External System | Protocol | Auth | Notes |
|-----------------|----------|------|-------|
| Zabbix API (6.0 / 6.4 / 7.0) | HTTPS JSON-RPC 2.0 | Bearer token (`Authorization: Bearer <token>`) or legacy `user.login` token in request body | API token preferred (available since Zabbix 5.4); fallback to session-based auth for 5.x is out of scope |
| LLM host (Claude Desktop, Cursor, etc.) | MCP over stdio (primary) | None (process isolation) | SSE transport is an optional secondary mode for network deployment |

### 3.5. Architectural Decisions (ADRs)

| Decision | Options Considered | Chosen Option | Rationale |
|----------|--------------------|---------------|-----------|
| MCP transport | stdio, SSE, WebSocket | stdio (primary), SSE (optional) | stdio is zero-infrastructure, secure by default, and the standard for local MCP deployments; SSE enables remote use without rewrite |
| Zabbix auth method | API token (header), session token (user.login), username+password | API token via env var | Stateless; no session expiry to manage; supported since Zabbix 5.4; most secure (NF-01) |
| HTTP client | `httpx`, `aiohttp`, `requests` | `httpx` (AsyncClient) | asyncio-native, supports HTTP/2, familiar API, same library used for MCP testing (NF-02) |
| Data validation | pydantic v2, dataclasses, TypedDict | pydantic v2 | Rich validation errors, serialization, settings management via `pydantic-settings`; full type inference (NF-08) |
| Configuration | YAML file, `.env` file, env vars | Environment variables only | 12-factor app compliance; avoids credential files on disk (NF-01, NF-07) |
| Multi-version Zabbix support | Runtime version detection, static branching, adapter pattern | Runtime version detection + conditional field mapping in pydantic models | Minimises code duplication; one client handles all versions; tested in CI matrix (NF-03) |
| Logging | `logging`, `loguru`, `structlog` | `structlog` | JSON output format; async-safe; easy key-value enrichment for tool name, duration, outcome (NF-06) |

---

## 4. Python Technology Stack

### 4.1. Core Stack

| Layer | Technology | Version (min) | Justification |
|-------|-----------|---------------|---------------|
| Runtime | Python | 3.11 | Required for `tomllib`, improved `asyncio` error messages, `Self` type; widely available in production |
| MCP framework | `mcp` (modelcontextprotocol/python-sdk) | 1.0 | Official SDK; provides tool registration, schema generation, stdio/SSE transport out of the box |
| Data validation | `pydantic` | 2.7 | Strict input validation for tool arguments (NF-04); used for API response models and settings (NF-07) |
| Settings | `pydantic-settings` | 2.3 | Env-var loading with type coercion and validation on startup; integrates with pydantic v2 models |
| HTTP client | `httpx` | 0.27 | asyncio-native async HTTP; used for Zabbix JSON-RPC calls (NF-02) and in test mocks |
| Logging | `structlog` | 24.1 | Structured JSON logging for auditability (NF-06); async-safe |

### 4.2. Key Libraries & Frameworks

| Purpose | Library | Justification |
|---------|---------|---------------|
| MCP server | `mcp[cli]` | Official Python MCP SDK; handles protocol, schema, and transport (F-01 through F-15) |
| Async HTTP | `httpx` | Required for non-blocking Zabbix API calls; supports timeouts and retries (NF-02) |
| Input validation | `pydantic` v2 | Validates all tool input parameters before reaching Zabbix; produces readable errors (NF-04) |
| Settings/config | `pydantic-settings` | Loads `ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_TIMEOUT_SECONDS`, `ZABBIX_PAGE_LIMIT` from env (NF-07) |
| Structured logging | `structlog` | Emits JSON log entries with tool name, duration, outcome for every call (NF-06) |
| CSV serialization | `csv` (stdlib) | Used for `export_metrics` CSV output (F-15); no extra dependency needed |
| Date/time handling | `python-dateutil` | Parses human-supplied date strings into Zabbix Unix timestamps for history/report tools (F-06, F-12) |

### 4.3. Infrastructure & DevOps

| Purpose | Tool | Justification |
|---------|------|---------------|
| Package manager & venv | `uv` | Fast dependency resolution; `uv run` entry point for MCP host config; PEP 621 `pyproject.toml` |
| Linting | `ruff` | Replaces flake8 + isort + pyupgrade in one fast tool; enforced in CI |
| Type checking | `mypy --strict` | Ensures full type safety across all tool handlers and client (NF-08) |
| Security scanning | `bandit` | Confirms no hardcoded credentials or unsafe patterns (NF-01) |
| Unit testing | `pytest` + `pytest-asyncio` | Standard async test runner; fixtures for mocked `httpx` responses |
| HTTP mocking | `respx` | Intercepts `httpx` requests in unit tests without patching; enables Zabbix API response simulation |
| Integration testing | `pytest` + Docker Compose | CI spins up Zabbix 6.0/6.4/7.0 containers; integration tests validate real API calls (NF-03) |
| Coverage | `pytest-cov` | Enforces ≥80 % coverage gate in CI (NF-08) |
| CI | GitHub Actions | Matrix build across Python 3.11/3.12 and Zabbix 6.0/6.4/7.0 |
| Containerisation | Docker + `python:3.11-slim` | Optional deployment image for SSE transport mode |

### 4.4. Project Structure

```
zabbix-mcp-server/
├── src/
│   └── zabbix_mcp/
│       ├── __init__.py
│       ├── server.py               # MCP server entry point; tool registration
│       ├── config.py               # Settings (pydantic-settings, env vars)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── problems.py         # get_active_problems, acknowledge_problem, get_incident_summary
│       │   ├── hosts.py            # add_host, search_hosts, check_host_availability
│       │   ├── metrics.py          # get_metric_value, get_metric_history, search_items, export_metrics
│       │   ├── maintenance.py      # create_maintenance
│       │   ├── triggers.py         # create_trigger, get_triggers
│       │   ├── reports.py          # get_availability_report
│       │   └── macros.py           # bulk_update_macro
│       └── zabbix/
│           ├── __init__.py
│           ├── client.py           # Async JSON-RPC client, pagination, retry, auth
│           ├── models.py           # Pydantic v2 DTOs for Zabbix API objects
│           └── errors.py           # ZabbixError hierarchy; error code → message mapping
├── tests/
│   ├── unit/
│   │   ├── tools/                  # Per-tool unit tests with mocked ZabbixClient
│   │   └── zabbix/                 # Client-level tests with respx HTTP mocks
│   └── integration/
│       ├── conftest.py             # Docker-based Zabbix fixture
│       └── test_*.py               # End-to-end tool tests against live Zabbix
├── docker-compose.test.yml         # Zabbix 6.0 / 6.4 / 7.0 test matrix
├── pyproject.toml                  # PEP 621 metadata, dependencies, tool config
├── .env.example                    # Documented env var template
└── README.md
```

---

## 5. Implementation Roadmap

| Phase | Scope | Deliverable | Effort Estimate |
|-------|-------|-------------|-----------------|
| MVP | F-01 (`get_active_problems`), F-02 (`acknowledge_problem`), F-03 (`create_maintenance`), F-04 (`add_host`), F-05 (`get_metric_value`); NF-01, NF-02, NF-04, NF-07; stdio transport only; Zabbix 6.0 + 7.0 support | Installable `zabbix-mcp-server` package, working with Claude Desktop and Cursor; README with setup guide | 5–7 days |
| v1.0 | F-06 (`get_metric_history`), F-07 (`search_hosts`), F-10 (`get_incident_summary`), F-11 (`bulk_update_macro`), F-12 (`get_availability_report`); NF-05 (idempotency), NF-06 (structured logging), NF-08 (≥80 % coverage, mypy strict) | Full 10-tool server; CI matrix; integration tests for all three Zabbix versions | 5–7 days |
| v1.1 | F-08 (`get_triggers`), F-09 (`create_trigger` with expression validation), F-13 (`search_items`), F-14 (`check_host_availability`), F-15 (`export_metrics`); SSE transport mode | Complete 12-tool server; optional Docker image for remote MCP deployment | 4–5 days |
| v2.0 | Natural-language trigger expression generation (LLM-assisted); smart alert grouping by root-cause analysis; ChatOps integration layer (Telegram/Slack bot skeleton over MCP tools) | Extended platform; documented extension API | 10–15 days |

---

## 6. Open Questions & Risks

| ID | Question / Risk | Impact | Mitigation |
|----|----------------|--------|------------|
| R-01 | Zabbix API response time for `history.get` over 30-day windows can reach 30–60 s (BA §3.6), exceeding the 5 s NF-02 budget | High — tool appears to hang; LLM timeout | Enforce `ZABBIX_PAGE_LIMIT` pagination; add streaming/chunked result return for `get_metric_history`; document expected latency for large ranges in tool description |
| R-02 | Trigger expression syntax differs between Zabbix 6.0 (legacy) and 6.4/7.0 (new expression format); `create_trigger` must handle both | Medium — wrong expression format silently fails or is rejected | Detect API version at startup; use version-appropriate expression format; unit-test both syntaxes |
| R-03 | API token authentication (`Authorization: Bearer`) was introduced in Zabbix 5.4; some organisations still run 5.2 or earlier | Low–Medium — server unusable for those users | Document minimum supported version as 6.0 LTS; add clear startup error if version check fails |
| R-04 | `bulk_update_macro` on 500+ hosts may generate many sequential API calls, causing slow responses | Medium — user experience degradation | Implement chunked `host.update` batch calls; add progress indication in tool response |
| R-05 | MCP stdio transport is a single-process model; concurrent LLM calls are serialised | Low — LLM hosts typically send one tool call at a time; no parallel concurrency expected | Document concurrency model; if SSE is used, ensure `asyncio` task isolation per request |
| R-06 | Lack of write-operation confirmation step could lead to unintended side effects (e.g. creating maintenance on wrong host group) | Medium — operational risk | Tool descriptions must be precise; idempotency checks (NF-05) limit duplicate creation damage; destructive operations return a confirmation summary before committing |

---

*Document generated by python-system-analyst based on `/Users/bereznevn/Documents/ProjectRepos/agentic-session/business-analysis.md`.*
