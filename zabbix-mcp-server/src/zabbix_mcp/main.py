"""CLI entry point — ``uv run zabbix-mcp`` starts the MCP server via stdio."""

from __future__ import annotations


def main() -> None:
    """Start the Zabbix MCP server using stdio transport.

    All configuration is read from environment variables. The server
    will exit with a non-zero code if required variables (ZABBIX_URL,
    ZABBIX_API_TOKEN) are missing or invalid.
    """
    from .server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
