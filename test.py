# test_client.py
import asyncio
from fastmcp import Client

async def main():
    async with Client("https://external-mcp-server.onrender.com/mcp", auth="oauth") as client:
        tools = await client.list_tools()
        print(tools)

asyncio.run(main())