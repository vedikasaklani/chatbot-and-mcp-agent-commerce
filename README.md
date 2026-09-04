# Agent Commerce Payment Automation

An AI-assisted commerce application that lets authenticated users discover products, manage a cart, place Razorpay orders, and retrieve payment links. The project also exposes the commerce capabilities through an OAuth-protected Model Context Protocol (MCP) server for external AI clients.

## Project Overview

The application is split into three deployed services:

- **Frontend** — static HTML/CSS/JavaScript browser client
- **FastAPI Backend** — authentication, commerce APIs, AI agent, database access, and Razorpay integration
- **MCP Server** — OAuth-protected MCP interface for external AI clients

PostgreSQL provides persistent application data, while WorkOS AuthKit/Connect handles the OAuth flow used by external MCP clients.

## Why This Project Is Useful

- **Conversational commerce:** an AI client can search products, manage carts, place orders, and retrieve payment links through tool calls.
- **FastAPI backend:** REST endpoints handle authentication, products, carts, orders, reviews, ratings, and Razorpay payments.
- **WorkOS-protected MCP:** external AI clients can access the same commerce operations through OAuth-protected MCP tools.
- **Persistent data:** SQLAlchemy and Alembic manage PostgreSQL models and schema migrations.
- **Browser client:** the `frontend/` directory contains a lightweight client for registration, login, cart management, and checkout.

## Architecture

```text
                         External AI Client
                                │
                                │ OAuth
                                ▼
                         WorkOS AuthKit
                                │
                                ▼
                    ┌────────────────────────┐
                    │      MCP Server        │
                    │ external/mcp_server.py │
                    │    Render Web Service  │
                    └────────────┬───────────┘
                                 │ HTTPS
                                 ▼
                    ┌────────────────────────┐
                    │     FastAPI Backend     │
                    │       api/main.py       │
                    │    Render Web Service   │
                    └──────────┬───────┬─────┘
                               │       │
                               ▼       ▼
                         PostgreSQL   Razorpay

                    ┌────────────────────────┐
                    │       Frontend         │
                    │       frontend/        │
                    │    Render Static Site  │
                    └────────────┬───────────┘
                                 │ HTTPS
                                 ▼
                           FastAPI Backend
```

## Repository Structure

| Component | Location | Purpose |
| --- | --- | --- |
| FastAPI API | `api/main.py` | Application entry point, routes, and middleware |
| Database | `database/` | SQLAlchemy models, database connection, and Alembic migrations |
| AI agent | `agent/` | AI/tool-calling logic |
| MCP server | `external/mcp_server.py` | OAuth-protected MCP tools for external clients |
| Browser client | `frontend/` | Static HTML/CSS/JavaScript frontend |
| MCP check | `test.py` | Verifies that the MCP server exposes the expected tools |

## Getting Started Locally

### Prerequisites

- Python 3.12+
- PostgreSQL
- [`uv`](https://docs.astral.sh/uv/)
- Razorpay credentials
- WorkOS/AuthKit credentials
- Groq credentials

### Install dependencies

From the repository root:

```bash
uv sync
```

### Environment variables

Create a local `.env` file.

Typical backend configuration:

```dotenv
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/database
GROQ_API_KEY=your-groq-key
WORKOS_API_KEY=your-workos-key
razorpay_key=your-razorpay-key
razorpay_secret=your-razorpay-secret
razorpay_webhook_secret=your-webhook-secret
```

For the MCP server, `BASE_URL` should point to the backend it calls:

```dotenv
BASE_URL=http://127.0.0.1:8000
```

When using the deployed backend, set `BASE_URL` to the deployed backend URL instead.

**Never commit `.env` files, API keys, passwords, or database credentials.**

## Database Setup

The application uses PostgreSQL with SQLAlchemy and Alembic.

Run the latest migrations from the repository root:

```bash
uv run alembic upgrade head
```

For a new deployment, run migrations against the deployment PostgreSQL database before relying on the API.

### Local vs. production database

Local development can use a local PostgreSQL URL:

```dotenv
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/database
```

The deployed FastAPI service should use the **Render PostgreSQL Internal Database URL** in its Render environment variables.

Do not hard-code the production database URL in source code or `alembic.ini`.

## Run the Backend Locally

From the repository root:

```bash
uv run uvicorn api.main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Run the MCP Server Locally

The MCP server uses Streamable HTTP.

From the repository root:

```bash
uv run python -m external.mcp_server
```

The MCP server uses port `9000` by default locally and uses the `PORT` environment variable when deployed to Render.

The server should bind to `0.0.0.0` and use the deployment port, for example:

```python
host="0.0.0.0"
port=int(os.environ.get("PORT", 9000))
```

## MCP Authentication with WorkOS

The MCP server uses WorkOS AuthKit through FastMCP's `AuthKitProvider`.

The high-level authentication flow is:

```text
External MCP Client
        │
        ▼
WorkOS AuthKit
        │
        │ external_auth_id
        ▼
Backend /auth/workos/login
        │
        ▼
Frontend login UI
        │
        │ existing email/password authentication
        ▼
Backend
        │
        │ /authkit/oauth2/complete
        ▼
WorkOS
        │
        ▼
OAuth flow completes
        │
        ▼
MCP Client receives OAuth credentials
```

The backend's GET endpoint accepts `external_auth_id`, redirects the user to the frontend login UI, and preserves that ID through the login flow. After successful authentication, the backend completes the WorkOS flow and returns the redirect supplied by WorkOS.

### WorkOS configuration

Configure the WorkOS Login URI to point to the **deployed backend**, for example:

```text
https://YOUR-BACKEND.onrender.com/auth/workos/login
```

The MCP server's AuthKit provider should use the real AuthKit domain and deployed MCP base URL:

```python
AuthKitProvider(
    authkit_domain="https://YOUR-PROJECT.authkit.app",
    base_url="https://YOUR-MCP.onrender.com",
)
```

Replace the placeholders with the values from your WorkOS project and Render services.

The MCP endpoint is:

```text
https://YOUR-MCP.onrender.com/mcp
```

## Render Deployment

The application is deployed as separate Render services.

### 1. FastAPI Backend

Create a **Web Service** using the repository root.

Recommended settings:

```text
Root Directory:        leave blank
Build Command:         pip install -r requirements.txt
Start Command:         uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Configure the required production environment variables in Render, including:

```text
DATABASE_URL
GROQ_API_KEY
WORKOS_API_KEY
razorpay_key
razorpay_secret
razorpay_webhook_secret
```

For the backend, use the **Render PostgreSQL Internal Database URL** for `DATABASE_URL`.

### 2. MCP Server

Create a separate **Web Service** using the same repository.

Because `external/mcp_server.py` imports shared project modules such as `security` and `database`, keep the Render Root Directory at the repository root rather than setting it to `external`.

Recommended settings:

```text
Root Directory:        leave blank
Build Command:         pip install -r external/requirements.txt
Start Command:         python -m external.mcp_server
```

Configure environment variables such as:

```text
BASE_URL=https://YOUR-BACKEND.onrender.com
WORKOS_AUTHKIT_DOMAIN=https://YOUR-PROJECT.authkit.app
MCP_BASE_URL=https://YOUR-MCP.onrender.com
```

The MCP service must bind to `0.0.0.0` and use Render's `PORT` environment variable.

### 3. Frontend

Create a **Static Site** for the `frontend/` directory.

For the current plain HTML/CSS/JavaScript frontend:

```text
Root Directory:        frontend
Build Command:         leave blank
Publish Directory:     .
```

Set the frontend API base URL to the deployed backend URL, for example:

```javascript
const API_BASE = "https://YOUR-BACKEND.onrender.com";
```

The frontend is not a Python application, so it does not require a `requirements.txt` file.

## Production Service URLs

The deployed services follow this pattern:

```text
Frontend
https://YOUR-FRONTEND.onrender.com

Backend
https://YOUR-BACKEND.onrender.com

MCP
https://YOUR-MCP.onrender.com/mcp
```

The backend is the shared API used by both the browser client and the MCP server.

## Verify MCP Tools

The repository includes `test.py` for checking MCP tool visibility.

Run from the repository root:

```bash
uv run python test.py
```

The check requires an OAuth-capable MCP client and helps distinguish MCP discovery/authentication problems from backend request failures.

The MCP server exposes tools including:

- `search_products`
- `get_product`
- `add_to_cart`
- `view_cart`
- `create_order`
- `get_payment_link`
- `check_order_status`
- `get_ratings`

## Main API Capabilities

The backend supports:

- Local user registration and login
- WorkOS OAuth login for external clients
- Product search and product details
- Cart creation and updates
- Customer and agent order creation
- Razorpay payment links and payment verification
- Product reviews and ratings
- AI-assisted commerce through `/chat`

## Payment Flow

Razorpay is used for payment processing after an order is created.

The backend is responsible for order creation, payment-link generation, webhook handling, and payment verification, while the AI/MCP layer can expose the appropriate commerce actions to an external client.

## Database Migration and Data Transfer

Schema changes should be managed through Alembic:

```bash
uv run alembic upgrade head
```

For moving an existing local PostgreSQL database to Render, PostgreSQL dump/restore can be used. When restoring into the managed Render database, restore without trying to recreate the local `postgres` ownership/privilege metadata, for example:

```bash
pg_restore --no-owner --no-privileges -d "YOUR_RENDER_EXTERNAL_DATABASE_URL" backup.dump
```

Use the Render **External Database URL** from the local machine for the transfer. The deployed backend should use the Render **Internal Database URL** afterward.

## Security Notes

- Keep `.env` files out of Git.
- Store production secrets in Render environment variables.
- Do not commit WorkOS, Groq, Razorpay, or database credentials.
- Do not expose database credentials in logs or API responses.
- Treat OAuth redirect URLs, bearer tokens, and MCP endpoints as sensitive security boundaries.
- Use sanitized logs when reporting deployment issues.

## Development Workflow

A typical local workflow is:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn api.main:app --reload
uv run python -m external.mcp_server
```

Then run the MCP verification check when needed:

```bash
uv run python test.py
```

## Maintainer and Contributions

This project is maintained by **vedikasaklani**.

To contribute:

1. Create a focused branch.
2. Make the smallest change needed.
3. Run the relevant checks.
4. Open a pull request describing the behavior change and validation.

Please keep secrets out of commits and avoid unrelated formatting changes.
