"""Small MCP server for the reconnection tests of McpClient (R-B3).

One tool, `pid`, returns the id of the server process, so a test can tell a restarted server from
the old one and kill it. With `--fail-if PATH` the server exits with code 1 at startup when PATH
exists: a test makes a restart fail by creating that file.
"""

import argparse
import os
import sys
from pathlib import Path

from fastmcp import FastMCP


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-if", type=Path)
    args = parser.parse_args()
    if args.fail_if is not None and args.fail_if.exists():
        return 1
    server = FastMCP("prova-riconnessione")

    @server.tool(name="pid", description="Id del processo del server.")
    def pid() -> dict:
        return {"pid": os.getpid()}

    server.run(transport="stdio", show_banner=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
