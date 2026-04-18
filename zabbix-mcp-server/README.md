# Zabbix MCP Server

A production-ready [Model Context Protocol](https://modelcontextprotocol.io) server that exposes 15 Zabbix monitoring operations as MCP tools, enabling LLM assistants (Claude Desktop, Cursor, etc.) to interact with Zabbix without manual API calls.

## Features

- **15 MCP tools** covering problems, hosts, metrics, triggers, maintenance, reports, and macros
- **Zabbix 6.0 / 6.4 / 7.0** compatible via runtime version detection
- **Async I/O** using `httpx` with connection pooling and configurable timeouts
- **Pagination** — automatically fetches all pages for large result sets
- **Idempotent creates** — `add_host` and `create_maintenance` safely re-invoke without duplication
- **Structured JSON logging** via `structlog` — every tool call logged with duration and outcome
- **No credentials in logs** — API token is never written to any output

## Requirements

- Python 3.11+
- pip (comes with Python)
- Zabbix 6.0+ with API token authentication enabled

## Quick Start

```bash
# 1. Clone and create a virtual environment
git clone <repo>
cd zabbix-mcp-server
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Upgrade pip (required: pip >= 22)
pip install --upgrade pip

# 3. Install the package
pip install -e .

# 4. Configure
cp .env.example .env
# Edit .env: set ZABBIX_URL and ZABBIX_API_TOKEN

# 5. Run
zabbix-mcp
```

## Configuration

All settings are loaded from environment variables (or a `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZABBIX_URL` | ✅ | — | Zabbix server URL |
| `ZABBIX_API_TOKEN` | ✅ | — | Zabbix API token |
| `ZABBIX_TIMEOUT_SECONDS` | ❌ | `10` | HTTP timeout in seconds |
| `ZABBIX_PAGE_LIMIT` | ❌ | `100` | Max objects per API page |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |

## Claude Desktop / Cursor Integration

Add to your MCP client config (use the full path to the `zabbix-mcp` binary inside the virtual environment):

```json
{
  "mcpServers": {
    "zabbix": {
      "command": "/path/to/zabbix-mcp-server/.venv/bin/zabbix-mcp",
      "env": {
        "ZABBIX_URL": "https://your-zabbix.example.com",
        "ZABBIX_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

> **Tip:** find the exact path after installation by running `which zabbix-mcp` (with the venv activated).

## Available Tools

| Tool | Description |
|------|-------------|
| `get_active_problems` | List active problems filtered by host, group, severity |
| `acknowledge_problem` | Acknowledge a problem with a mandatory comment |
| `create_maintenance` | Create a maintenance window for hosts or groups |
| `add_host` | Add a host with interfaces, groups, and templates (idempotent) |
| `get_metric_value` | Get the current value of a metric by host + item key |
| `get_metric_history` | Fetch metric history over a time range |
| `search_hosts` | Search hosts by name, group, template, or tag |
| `get_triggers` | List triggers configured on a host |
| `create_trigger` | Create a trigger with expression validation |
| `get_incident_summary` | Incident summary with host list and event timeline |
| `bulk_update_macro` | Update a macro value across many hosts at once |
| `get_availability_report` | Uptime percentage per host over a calendar period |
| `search_items` | Search metrics by name, key, or description |
| `check_host_availability` | Check Zabbix agent reachability for a host |
| `export_metrics` | Export metric history as JSON or CSV |

## Development

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Upgrade pip (required: pip >= 22)
pip install --upgrade pip

# Install all dependencies (including dev)
pip install -r requirements-dev.txt
pip install -e .

# Run tests
pytest

# Run tests with coverage
pytest --cov

# Type checking
mypy --strict src/

# Linting
ruff check src/ tests/

# Security scan
bandit -r src/ -t B105,B106,B107,B108
```

## Architecture

```
LLM Host (Claude / Cursor)
       │ MCP Protocol (stdio)
┌──────▼──────────────────┐
│   MCP Transport Layer    │  mcp SDK (FastMCP)
├─────────────────────────┤
│   Tools Layer (15 tools) │  tools/*.py  — pure async functions
├─────────────────────────┤
│  Zabbix API Client       │  zabbix/client.py — httpx AsyncClient
├─────────────────────────┤
│   Configuration Layer    │  config.py — pydantic-settings
└─────────────────────────┘
       │ HTTPS / JSON-RPC 2.0
  Zabbix API (6.0 / 6.4 / 7.0)
```
