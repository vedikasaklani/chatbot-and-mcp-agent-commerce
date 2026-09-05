# AI Commerce Agent

An e-commerce system designed to be operated by both **people and AI agents**.

The project combines a traditional commerce backend with an AI agent and a **Model Context Protocol (MCP)** interface. A user can browse products, manage a cart, place orders, and initiate payments through the web application or conversationally **through the agent**.

External AI clients can access the same commerce capabilities **through MCP**.

The core design principle is:

> **The agent decides what to do. The backend decides how it is done.**

The FastAPI backend remains the source of truth for authentication, commerce logic, database operations, and payments. The AI and MCP layers sit on top of it rather than implementing separate commerce systems.

---

## Architecture

```text
                         ┌──────────────────────┐
                         │     Web Frontend     │
                         │      HTML / JS       │
                         └──────────┬───────────┘
                                    │
                                    │ HTTP + JWT
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                       │
│                                                             │
│  Authentication   Products   Cart   Orders   Reviews       │
│                                                             │
│                         /chat                               │
│                           │                                 │
│                           ▼                                 │
│                     Internal Agent                          │
│                     ┌────────────┐                          │
│                     │    LLM     │                          │
│                     └─────┬──────┘                          │
│                           │                                  │
│                      Tool calls                              │
│                           │                                  │
│                           ▼                                  │
│                    Commerce Tools                            │
└───────────────┬─────────────────────┬──────────────────────┘
                │                     │
                ▼                     ▼
          PostgreSQL               Razorpay
                ▲
                │
                │ HTTP
                │
        ┌───────┴────────┐
        │ CommerceClient │
        └───────▲────────┘
                │
        ┌───────┴────────┐
        │   MCP Server   │
        │ external/      │
        │ mcp_server.py  │
        └───────▲────────┘
                │
             MCP/OAuth
                │
        ┌───────┴────────┐
        │ External AI    │
        │ Client         │
        └────────────────┘
```

There are two ways an AI agent can interact with the commerce system:

### Internal agent

The chatbot is part of the FastAPI application.

```text
User
 │
 ▼
POST /chat
 │
 ▼
AI Agent
 │
 ▼
LLM chooses a tool
 │
 ▼
Agent Tool
 │
 ▼
Commerce API
 │
 ▼
PostgreSQL / Razorpay
```

### External MCP agent

An external AI client connects through MCP.

```text
External AI Client
 │
 │ MCP + OAuth
 ▼
MCP Server
 │
 ▼
CommerceClient
 │
 │ HTTP + JWT
 ▼
FastAPI Backend
 │
 ▼
PostgreSQL / Razorpay
```

Both paths eventually use the **same FastAPI commerce API**.

This avoids duplicating business logic between the chatbot, MCP server, and web application.

---

# Why this architecture?

A language model should not be responsible for directly changing application state.

For example, when a user says:

> "Find me a laptop under ₹50,000 and add the best one to my cart."

the agent can reason about what needs to happen:

```text
search_products()
       ↓
get_product()
       ↓
add_to_cart()
```

But the actual operations are performed by the backend.

```text
LLM
 │
 │ decides
 ▼
Tool
 │
 │ requests
 ▼
FastAPI
 │
 │ validates + executes
 ▼
Database
```

This separation gives the system a clear boundary:

* **LLM** — reasoning and tool selection
* **Agent tools** — translate model requests into application operations
* **FastAPI** — authentication, validation, business logic, and side effects
* **PostgreSQL** — persistent state
* **Razorpay** — payment processing
* **MCP** — standard interface for external AI clients

---

# Repository Structure

```text
.
├── agent/
│   ├── agent.py
│   ├── agent_tools.py
│   └── prompts.py
│
├── api/
│   ├── main.py
│   ├── auth.py
│   ├── dependencies.py
│   ├── cart_service.py
│   ├── reviews.py
│   ├── razorpay_integration.py
│   └── razorpay_payment_webhook.py
│
├── database/
│   ├── database.py
│   ├── database_models.py
│   ├── models.py
│   └── alembic/
│
├── external/
│   ├── mcp_server.py
│   └── requirements.txt
│
├── frontend/
│   └── HTML / CSS / JavaScript
│
├── tests/
│
├── utils/
│
├── commerce_client.py
├── security.py
├── pyproject.toml
└── uv.lock
```

### `api/`

The main application layer.

It contains the FastAPI application, authentication, cart logic, reviews, orders, and Razorpay integration.

This is where the application's actual commerce rules live.

### `agent/`

Contains the internal AI agent.

* `agent.py` — agent execution and tool-calling loop
* `agent_tools.py` — tools exposed to the LLM
* `prompts.py` — agent instructions/prompts

The agent can call commerce operations, but it does not directly access the database.

### `commerce_client.py`

A thin HTTP client used to communicate with the FastAPI commerce API.

It creates an explicit boundary between agent-facing code and backend implementation.

```text
Agent / MCP
     │
     ▼
CommerceClient
     │
     ▼
FastAPI
```

### `external/`

Contains the MCP server.

`mcp_server.py` exposes commerce functionality as MCP tools for external AI clients.

The MCP tools use `CommerceClient` instead of implementing their own database or commerce logic.

### `database/`

Contains SQLAlchemy database configuration/models and Alembic migrations.

PostgreSQL stores both commerce state and agent-related state such as conversation sessions.

### `frontend/`

The browser-facing application.

It communicates with the FastAPI backend over HTTP.

### `security.py`

Contains application-level JWT authentication and user resolution.

---

# Agent Architecture

The internal agent is implemented as a bounded tool-calling loop.

Conceptually:

```text
                     User Message
                          │
                          ▼
                    ┌───────────┐
                    │    LLM    │
                    └─────┬─────┘
                          │
                 ┌────────┴────────┐
                 │                 │
          normal response       tool call
                                   │
                                   ▼
                             execute_tool()
                                   │
                                   ▼
                            Commerce API
                                   │
                                   ▼
                                result
                                   │
                                   └──────► LLM
                                              │
                                              ▼
                                       Final response
```

The agent does not blindly execute an unlimited number of calls. Its tool-calling process is bounded by a maximum number of turns.

This prevents a malformed model response from creating an unbounded execution loop.

---

# Agent Tools

The tools exposed to the internal agent correspond to commerce operations such as:

```text
search_products
get_product
add_to_cart
remove_from_cart
view_cart
create_order
get_payment_link
check_order_status
get_ratings
```

The important part is what happens after the LLM chooses one.

For example:

```text
LLM
 │
 │ search_products(...)
 ▼
Agent Tool
 │
 ▼
CommerceClient
 │
 │ HTTP
 ▼
GET /products
 │
 ▼
FastAPI
 │
 ▼
PostgreSQL
```

The agent therefore behaves like an authenticated API client rather than having privileged access to application internals.

---

# MCP Architecture

The MCP server exposes the commerce capabilities to external AI clients.

```text
┌──────────────────┐
│   External AI    │
└────────┬─────────┘
         │
         │ MCP
         ▼
┌──────────────────┐
│   MCP Server     │
│                  │
│ MCP tool layer   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ CommerceClient   │
└────────┬─────────┘
         │
         │ HTTP
         ▼
┌──────────────────┐
│ FastAPI Backend  │
└──────────────────┘
```

The MCP layer is therefore an **interoperability layer**, not a second backend.

This makes the MCP interface relatively thin:

```text
MCP tool
   ↓
CommerceClient
   ↓
FastAPI endpoint
```

The same backend validation and authorization rules apply regardless of whether the request originated from the frontend, internal agent, or MCP client.

---

# Authentication

The application uses JWT-based authentication for its normal API access.

```text
User Login
    │
    ▼
JWT
    │
    ▼
FastAPI
    │
    ▼
Authenticated User
```

For external MCP access, WorkOS AuthKit is used for the OAuth flow.

The important distinction is:

```text
WorkOS
  │
  │ authenticates external identity
  ▼
MCP Server
  │
  │ maps identity to application user
  ▼
Application JWT
  │
  ▼
FastAPI
```

This allows external AI clients to enter the same authorization model used by the rest of the application.

---

# Conversation State

The chatbot maintains conversation state using a `ConversationSession`.

A simplified flow is:

```text
User
 │
 ▼
/chat
 │
 ▼
Find user's conversation session
 │
 ▼
Load previous messages
 │
 ▼
Run agent
 │
 ├── user message
 ├── assistant messages
 ├── tool calls
 └── tool results
 │
 ▼
Persist updated conversation
```

The session is persisted in PostgreSQL rather than existing only in the process memory of the FastAPI server.

The agent also uses a bounded context window/idle timeout so that conversations do not grow indefinitely.

---

# Agent Decision Records

When an agent creates an order, the application can associate a structured decision record with that order.

The flow is:

```text
User Request
     │
     ▼
Agent
     │
     ├── tool call
     ├── tool call
     └── create_order
              │
              ▼
            Order
              │
              ▼
       Decision Record
```

The record captures information from the agent execution, including the request, tool trace, and resulting decision.

This provides a basic audit trail for agent-driven commerce actions.

---

# Payments

Payment processing is deliberately kept outside the agent.

The agent can request operations such as:

```text
create_order()
get_payment_link()
check_order_status()
```

but the actual payment workflow is implemented by the backend.

```text
Agent
 │
 ▼
FastAPI
 │
 ▼
Razorpay
 │
 ▼
Payment
 │
 ▼
Webhook
 │
 ▼
FastAPI
 │
 ▼
Order state
```

This keeps payment state deterministic and backend-controlled.

The LLM can initiate a valid application operation, but it does not decide whether a payment has actually succeeded.

---

# Data Flow Example

Consider:

> "Show me products under ₹2,000 and add one to my cart."

The complete request path is:

```text
                    User
                     │
                     ▼
                  /chat
                     │
                     ▼
                Internal Agent
                     │
                     ▼
                    LLM
                     │
              search_products
                     │
                     ▼
              Commerce Client
                     │
                     ▼
                FastAPI API
                     │
                     ▼
                 PostgreSQL
                     │
                     ▼
               Search results
                     │
                     ▼
                    LLM
                     │
              chooses product
                     │
                     ▼
               add_to_cart
                     │
                     ▼
                FastAPI API
                     │
                     ▼
                 PostgreSQL
                     │
                     ▼
                Agent response
```

An external MCP client follows the same backend path:

```text
External AI
     │
     ▼
     MCP
     │
     ▼
MCP Server
     │
     ▼
CommerceClient
     │
     ▼
FastAPI
     │
     ▼
PostgreSQL
```

The interface changes; the underlying commerce system does not.

---

# Technology Stack

| Layer                  | Technology                       |
| ---------------------- | -------------------------------- |
| Frontend               | HTML, CSS, JavaScript            |
| Backend                | FastAPI                          |
| Language               | Python                           |
| AI Model               | Groq                             |
| Agent                  | Custom Python tool-calling agent |
| Agent Interoperability | Model Context Protocol           |
| MCP Transport          | Streamable HTTP                  |
| Authentication         | JWT + WorkOS AuthKit             |
| Database               | PostgreSQL                       |
| ORM                    | SQLAlchemy                       |
| Migrations             | Alembic                          |
| Payments               | Razorpay                         |
| Deployment             | Render                           |
| Package Management     | `uv`                             |

---

# Quick Start

## 1. Clone the repository

```bash
git clone https://github.com/vedikasaklani/chatbot-and-mcp-agent-commerce.git
cd chatbot-and-mcp-agent-commerce
```

## 2. Install dependencies

The project uses `uv`.

```bash
uv sync
```

## 3. Configure environment variables

Create your environment configuration with the credentials required by the application.

The main integrations require configuration for:

```text
DATABASE_URL
GROQ_API_KEY
WORKOS_*
RAZORPAY_*
```

Use the project's existing environment configuration as the source of truth for the exact variable names.

Do not commit secrets to Git.

## 4. Run database migrations

```bash
uv run alembic upgrade head
```

## 5. Start the FastAPI backend

```bash
uv run uvicorn api.main:app --reload
```

The API runs locally on port `8000`.

FastAPI's interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## 6. Start the MCP server

Run the MCP service separately:

```bash
uv run python -m external.mcp_server
```

The MCP service uses port `9000`.

For local external access, an HTTPS tunnel such as ngrok may be required depending on the MCP client being used.

---

# Configuration

The application depends on several external services:

### PostgreSQL

Stores application and conversation state.

### Groq

Provides the LLM used by the internal agent.

### WorkOS

Provides authentication/OAuth for external MCP access.

### Razorpay

Handles payment creation and payment status/webhooks.

### Render

The deployed application separates the frontend, backend, and MCP server into independently running services.

---

# Development

When modifying the project, keep the dependency direction in mind:

```text
Frontend
    │
    ▼
FastAPI
    │
    ├── Database
    ├── Razorpay
    │
    └── Agent
          │
          ▼
     CommerceClient
```

For MCP changes:

```text
MCP Server
    │
    ▼
CommerceClient
    │
    ▼
FastAPI
```

Prefer extending the existing backend API rather than implementing the same business operation independently inside the MCP server or agent.

---

# Contributing

When adding a new commerce capability:

1. Implement the business operation in the FastAPI/backend layer.
2. Add or update the appropriate database models/migrations if persistent state is required.
3. Expose the operation through the API.
4. Add it to the internal agent tools if the agent should use it.
5. Add it to the MCP server if external AI clients should use it.
6. Add tests for the backend behaviour and agent/MCP integration where appropriate.

The goal is to keep the architecture centralized:

```text
             New Capability
                   │
                   ▼
            FastAPI Backend
             /           \
            /             \
           ▼               ▼
    Internal Agent       MCP Server
```

not:

```text
        New Capability
          /    |    \
         ▼     ▼     ▼
      Agent   MCP   Backend
      logic   logic   logic
```

The second approach creates duplicated business rules and makes the system harder to maintain.

---

# Design Principles

### Backend owns state

Products, carts, orders, users, and payments are backend concerns.

### Agents own reasoning

The LLM determines which available operation is useful and interprets the result.

### Tools are controlled interfaces

Agent tools translate model actions into authenticated application requests.

### MCP is an interoperability boundary

MCP allows external AI clients to use the commerce system without exposing the internal implementation.

### Authentication follows the request

Agent and MCP requests still resolve to an authenticated application user before accessing protected commerce operations.

### Payments remain deterministic

Payment verification and order state transitions are handled by the backend and payment provider, not by the LLM.

---

# The Big Picture

This project can be summarized as:

```text
              ┌─────────────────────┐
              │     Human User      │
              └──────────┬──────────┘
                         │
                    Web / Chat
                         │
                         ▼
              ┌─────────────────────┐
              │   FastAPI Backend   │◄──────────────┐
              │                     │               │
              │  Commerce + Auth    │               │
              └─────────┬───────────┘               │
                        │                            │
               ┌────────┴────────┐                   │
               ▼                 ▼                   │
          PostgreSQL          Razorpay               │
                                                     │
                                            CommerceClient
                                                     ▲
                                                     │
                                                MCP Server
                                                     ▲
                                                     │
                                              External AI
```

The system is therefore not simply **“a chatbot for an online store.”**

It is a **centralized commerce backend with multiple AI interfaces**:

* a built-in tool-calling agent for conversational commerce
* an MCP server for external AI agents
* a conventional web frontend for direct human interaction

All three ultimately rely on the same application layer, authentication model, database, and payment infrastructure.
