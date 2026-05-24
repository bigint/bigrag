from __future__ import annotations

import argparse
import asyncio
import os
import sys

from mcp.server.fastmcp import FastMCP

from .register import register, shared_client_provider
from .tools import (
    discover_scope,
    make_client,
    scoped_instructions,
    unscoped_instructions,
)


def create_server(
    base_url: str,
    api_key: str | None,
    collection: str | None = None,
    port: int = 6101,
) -> FastMCP:
    mcp = FastMCP(
        name=f"bigrag-{collection}" if collection else "bigrag",
        instructions=scoped_instructions(collection) if collection else unscoped_instructions(),
        port=port,
    )
    client = make_client(base_url, api_key)
    register(mcp, shared_client_provider(client), collection)
    return mcp


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="bigrag-mcp",
        description=(
            "bigRAG MCP server — expose a bigRAG instance over the Model Context Protocol. "
            "The toolset is scoped automatically from the API key: collection-pinned keys "
            "get a collection-scoped server."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIGRAG_URL", "http://localhost:4000"),
        help="bigRAG server URL (env: BIGRAG_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("BIGRAG_API_KEY"),
        help="bigRAG API key (env: BIGRAG_API_KEY)",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6101,
        help="Port for streamable-http transport (default: 6101)",
    )
    args = parser.parse_args()

    if not args.api_key:
        sys.stderr.write(
            "bigrag-mcp: warning — no API key set (env BIGRAG_API_KEY or --api-key). "
            "Requests will be unauthenticated and will fail on protected endpoints.\n"
        )
        collection: str | None = None
    else:

        async def _probe() -> str | None:
            async with make_client(args.base_url, args.api_key) as c:
                return await discover_scope(c)

        try:
            collection = asyncio.run(_probe())
        except RuntimeError as e:
            sys.stderr.write(f"bigrag-mcp: {e}\n")
            sys.exit(1)

    server = create_server(args.base_url, args.api_key, collection, port=args.port)
    if args.transport == "stdio":
        server.run()
    else:
        server.run(transport="streamable-http")


if __name__ == "__main__":
    cli()
