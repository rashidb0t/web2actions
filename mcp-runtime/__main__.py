"""
Entry point for the Web2Actions MCP runtime.

Usage:
    python -m mcp-runtime <connector-definition.json>

Reads the connector definition, then serves it over stdio as an MCP server.
"""

import asyncio
import json
import sys


async def _main(connector_file: str) -> None:
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from serve import run_stdio

    with open(connector_file, "r", encoding="utf-8") as file:
        connector = json.load(file)
    await run_stdio(connector)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m mcp-runtime <connector-definition.json>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(_main(sys.argv[1]))