import os

from starlette.middleware import Middleware

from external.mcp_server import StripTrailingSlashMiddleware, mcp

if __name__ == "__main__":
    mcp.run(transport="stdio",
            host="0.0.0.0",
                    port=int(os.environ.get("PORT", "9000")),
                    middleware=[Middleware(StripTrailingSlashMiddleware)])