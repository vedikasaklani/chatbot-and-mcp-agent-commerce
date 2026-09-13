import os

from starlette.middleware import Middleware

from external.mcp_server import StripTrailingSlashMiddleware, mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
