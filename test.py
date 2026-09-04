import asyncio
from fastmcp import Client

MCP_SERVER_URL = "https://external-mcp-server.onrender.com/mcp"
EXPECTED_TOOLS = {
    "search_products",
    "get_product",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "create_order",
    "get_payment_link",
    "check_order_status",
    "get_ratings",
}


async def main() -> None:
    async with Client(MCP_SERVER_URL, auth="oauth") as client:
        tools = await client.list_tools()
        visible_tools = {tool.name for tool in tools}

        print(f"Server: {MCP_SERVER_URL}")
        print(f"Visible tools ({len(visible_tools)}): {sorted(visible_tools)}")

        if not visible_tools:
            raise AssertionError("The MCP server returned no visible tools.")

        missing_tools = EXPECTED_TOOLS - visible_tools
        if missing_tools:
            raise AssertionError(
                f"Expected tools are missing from the server: {sorted(missing_tools)}"
            )

        print("PASS: all expected MCP tools are visible.")


if __name__ == "__main__":
    asyncio.run(main())