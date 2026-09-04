# Agent Commerce Payout Automation

An AI-assisted commerce application that lets authenticated users discover products, manage a cart, place Razorpay orders, and retrieve payment links. The project also exposes the commerce actions as OAuth-protected Model Context Protocol (MCP) tools for external AI clients.

## Why This Project Is Useful

- **Conversational commerce**: the agent can search products, update carts, and place orders through tool calls.
- **FastAPI backend**: REST endpoints handle authentication, products, carts, orders, reviews, and Razorpay payments.
- **MCP integration**: external clients can use the same commerce capabilities through a WorkOS/AuthKit-protected server.
- **Persistent order workflow**: SQLAlchemy and Alembic manage PostgreSQL data and schema migrations.
- **Static frontend**: the `frontend/` directory contains a lightweight browser client for login, chat, cart management, and checkout.

## Architecture

| Component | Location | Purpose |
| --- | --- | --- |
| FastAPI API | `api/main.py` | Application routes and middleware |
| Database models and migrations | `database/` | SQLAlchemy models and Alembic revisions |
| AI agent | `agent/` | Groq-compatible tool-calling loop |
| MCP server | `external/mcp_server.py` | OAuth-protected MCP tools for external clients |
| Browser client | `frontend/` | Static JavaScript frontend |
| MCP visibility check | `test.py` | Verifies the deployed server exposes expected tools |

## Getting Started

### Prerequisites

- Python 3.12 or newer
- PostgreSQL
- [`uv`](https://docs.astral.sh/uv/)
- Razorpay, WorkOS/AuthKit, and Groq credentials for the corresponding features

### Install

```bash
uv sync
```

Copy the required configuration into a local `.env` file. At minimum, the backend expects:

```dotenv
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/database
GROQ_API_KEY=your-groq-key
WORKOS_API_KEY=your-workos-key
razorpay_key=your-razorpay-key
razorpay_secret=your-razorpay-secret
razorpay_webhook_secret=your-webhook-secret
```

Never commit `.env` files or credentials.

### Prepare the database

Configure Alembic to use the same PostgreSQL URL as the application, then run:

```bash
uv run alembic upgrade head
```

### Run the API

From the repository root:

```bash
uv run uvicorn api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. FastAPI's interactive documentation is available at `/docs`.

### Run the MCP server

```bash
uv run python external/mcp_server.py
```

Set `BASE_URL` when the MCP server needs to call a remote backend:

```bash
BASE_URL=https://backend-fastapi-bktw.onrender.com uv run python external/mcp_server.py
```

The MCP server uses the `PORT` environment variable when deployed and defaults to port `9000` locally.

### Verify MCP tools

The check requires an OAuth-capable MCP client:

```bash
uv run python test.py
```

It verifies that the expected product, cart, order, payment, and ratings tools are visible.

## Main Capabilities

The backend provides routes for:

- Local and WorkOS authentication
- Product search and product details
- Cart creation, updates, and removal
- Customer and agent order creation
- Razorpay payment links and payment verification
- Product reviews and ratings
- AI chat through `/chat`

The MCP server exposes these operations as tools including `search_products`, `get_product`, `add_to_cart`, `view_cart`, `create_order`, `get_payment_link`, `check_order_status`, and `get_ratings`.

## Deployment Notes

- Deploy the FastAPI application with the start target `api.main:app`.
- Run database migrations against the deployment PostgreSQL instance before starting the API.
- Configure WorkOS/AuthKit callback URLs to match the deployed MCP server and frontend.
- Set the frontend API base URL in `frontend/app.js` to the deployed backend before publishing the static files.
- Keep backend credentials and database URLs in the hosting provider's environment settings.

## Getting Help

- Use FastAPI's local `/docs` endpoint to inspect available API schemas.
- Check the service logs first for database migration, OAuth callback, and Razorpay errors.
- Run `test.py` to distinguish MCP tool discovery problems from backend request failures.
- Open an issue in the project repository with the failing endpoint, status code, and sanitized logs. Do not include tokens, passwords, or private database URLs.

## Maintainer and Contributions

This project is maintained by **vedikasaklani**.

To contribute:

1. Create a focused branch.
2. Make the smallest change that addresses the issue.
3. Run the relevant checks, such as `uv run python test.py` or a targeted test.
4. Open a pull request describing the behavior change and validation performed.

Please keep secrets out of commits and avoid unrelated formatting changes.
