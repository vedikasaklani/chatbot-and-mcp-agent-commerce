# Agent Commerce

### An e-commerce backend built for both humans and AI agents.

Traditional e-commerce APIs are designed for applications.

This project makes the same commerce capabilities available to **AI agents** — without giving an LLM direct control over application state.

A user can browse products, manage a cart, place an order, and initiate payment through the web application or conversationally through the built-in AI agent. External AI clients can perform the same operations through an **OAuth-protected MCP server**.

The core idea is simple:

> **The agent decides what to do. The backend decides whether and how it happens.**

---

## The Architecture

```text
                         HUMAN USER
                             │
                    Web Application
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                       │
│                                                              │
│   Auth │ Products │ Cart │ Orders │ Reviews │ Payments       │
│                                                              │
│                         /chat                                │
│                           │                                  │
│                           ▼                                  │
│                     INTERNAL AGENT                           │
│                           │                                  │
│                           ▼                                  │
│                          LLM                                 │
│                           │                                  │
│                      Tool calls                              │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            │
                       Commerce API
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
             PostgreSQL             Razorpay


        EXTERNAL AI CLIENT
                │
             OAuth
                │
                ▼
          ┌───────────┐
          │ MCP Server│
          └─────┬─────┘
                │
                ▼
         CommerceClient
                │
             HTTP + JWT
                │
                ▼
          FASTAPI BACKEND
```

There are **multiple ways into the system, but only one commerce authority**.

The frontend, internal agent, and external MCP clients ultimately rely on the same backend for authentication, validation, persistence, orders, and payments.

---

# Why this matters

Giving an LLM direct access to a database or payment system would make the model responsible for things it should not control.

Instead, this project creates a deterministic boundary:

```text
┌──────────────────────────────┐
│        AI / LLM Layer        │
│                              │
│  Understand intent           │
│  Select tools                │
│  Interpret results           │
└──────────────┬───────────────┘
               │
          Tool interface
               │
               ▼
┌──────────────────────────────┐
│       Application Layer      │
│                              │
│  Authentication              │
│  Validation                  │
│  Business rules              │
│  Authorization               │
│  State changes                │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       System of Record       │
│                              │
│  PostgreSQL                  │
│  Razorpay                    │
└──────────────────────────────┘
```

The LLM can **request**:

```text
create_order(...)
```

but it cannot simply decide:

```text
"the payment succeeded"
```

The backend and payment provider determine the actual state.

This separation is what allows an AI agent to participate in real commerce without making the AI itself the source of truth.

---

# One Commerce API, Two Agent Interfaces

The project has two distinct agent paths.

## 1. Built-in AI Agent

The internal chatbot lives in `agent/`.

A request such as:

> "Find me a laptop under ₹50,000 and add the best one to my cart."

becomes a sequence of tool calls:

```text
User
 │
 ▼
POST /chat
 │
 ▼
LLM
 │
 ├── search_products()
 │
 ├── get_product()
 │
 └── add_to_cart()
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

The model handles reasoning and tool selection.

The API handles the actual operation.

The agent therefore behaves like an **authenticated API client**, rather than having privileged access to the database.

---

## 2. External AI through MCP

The same commerce capabilities are exposed through the **Model Context Protocol**.

```text
External AI Client
        │
        │ MCP
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

The MCP server does not create a second implementation of the store.

It translates MCP tool calls into requests against the existing commerce API.

This means an external agent can use operations such as:

```text
search_products
get_product
view_cart
add_to_cart
remove_from_cart
create_order
get_payment_link
check_order_status
get_ratings
```

while the backend continues to enforce the same application rules.

---

# Authentication: From External Identity to Application Identity

External MCP access is protected with **WorkOS AuthKit / OAuth**.

The important part is that external authentication does not bypass the application's existing authorization model.

```text
External AI Client
        │
        ▼
   WorkOS OAuth
        │
        ▼
    MCP Server
        │
        │ identify user
        ▼
 Application User
        │
        ▼
    Backend JWT
        │
        ▼
     FastAPI
```

Once the external identity has been mapped to an application user, requests reach the backend using the same JWT-based authentication mechanism used by the application.

So the MCP layer is not a privileged backdoor into the database.

---

# Agent State Is Persistent

The chatbot is not just a stateless prompt/response wrapper.

Conversation sessions are persisted in PostgreSQL.

```text
ConversationSession
        │
        ├── user message
        ├── assistant message
        ├── tool call
        ├── tool result
        └── next turn
```

The agent can therefore maintain conversational context across requests.

The session handling also includes concurrency protection and bounded context/idle behaviour, preventing the conversation from becoming an unbounded accumulation of messages.

---

# Agent Actions Can Be Traced

When the agent creates an order, the application extracts information from the agent's execution trace and associates a structured decision record with the order.

```text
User Request
     │
     ▼
   Agent
     │
     ├── search_products()
     ├── get_product()
     ├── add_to_cart()
     └── create_order()
              │
              ▼
            Order
              │
              ▼
       Decision Record
```

This gives agent-driven commerce actions a record of **what the user asked for, what the agent did, and what operation resulted in the order**.

The purpose is not to make the LLM authoritative.

It is the opposite:

> **Agent reasoning can be recorded while application state remains backend-controlled.**

---

# Payments Stay Deterministic

Payments are handled by the backend through Razorpay.

The agent can initiate commerce operations such as:

```text
create_order()
get_payment_link()
check_order_status()
```

but the payment lifecycle remains outside the model:

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

The LLM can ask the system to perform an operation.

It cannot manufacture a successful payment result.

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

### Core responsibilities

| Component            | Responsibility                                                |
| -------------------- | ------------------------------------------------------------- |
| `api/`               | Commerce API, authentication, orders, cart, reviews, payments |
| `agent/`             | LLM reasoning and tool-calling loop                           |
| `commerce_client.py` | HTTP interface between agent-facing code and the backend      |
| `external/`          | MCP interface for external AI clients                         |
| `database/`          | SQLAlchemy models, persistence, and migrations                |
| `security.py`        | JWT authentication                                            |
| `frontend/`          | Human-facing web application                                  |
| `tests/`             | Application and integration tests                             |

---

# Request Lifecycle

A normal conversational purchase looks like this:

```text
"Add a good laptop under ₹50,000 to my cart."
                  │
                  ▼
             /chat
                  │
                  ▼
              AI Agent
                  │
                  ▼
                 LLM
                  │
           chooses tools
                  │
                  ▼
          search_products()
                  │
                  ▼
           FastAPI /products
                  │
                  ▼
              PostgreSQL
                  │
                  ▼
             search result
                  │
                  ▼
                 LLM
                  │
                  ▼
           add_to_cart()
                  │
                  ▼
            FastAPI /cart
                  │
                  ▼
              PostgreSQL
                  │
                  ▼
           Final response
```

An external AI client follows the same underlying commerce path:

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
     ├── PostgreSQL
     └── Razorpay
```

The **interface changes; the commerce system does not**.

---

# Technology Stack

| Layer              | Technology                       |
| ------------------ | -------------------------------- |
| Backend            | FastAPI                          |
| Language           | Python                           |
| AI                 | Groq                             |
| Agent              | Custom Python tool-calling agent |
| Agent Protocol     | Model Context Protocol           |
| MCP Transport      | Streamable HTTP                  |
| Authentication     | JWT + WorkOS AuthKit             |
| Database           | PostgreSQL                       |
| ORM                | SQLAlchemy                       |
| Migrations         | Alembic                          |
| Payments           | Razorpay                         |
| Frontend           | HTML, CSS, JavaScript            |
| Package Management | `uv`                             |
| Deployment         | Render                           |

---

# Quick Start

## Prerequisites

* Python 3.12+
* PostgreSQL
* `uv`
* API credentials for Groq
* WorkOS credentials for external MCP authentication
* Razorpay credentials for payment functionality

## 1. Clone

```bash
git clone https://github.com/vedikasaklani/chatbot-and-mcp-agent-commerce.git
cd chatbot-and-mcp-agent-commerce
```

## 2. Install dependencies

```bash
uv sync
```

## 3. Configure environment variables

Configure the credentials required by the application:

```text
DATABASE_URL
GROQ_API_KEY
WORKOS_*
RAZORPAY_*
```

Use the project's environment configuration as the source of truth for the exact variable names.

Never commit secrets.

## 4. Run migrations

```bash
uv run alembic upgrade head
```

## 5. Start the API

```bash
uv run uvicorn api.main:app --reload
```

The API will be available on:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## 6. Start the MCP server

In a separate terminal:

```bash
uv run python -m external.mcp_server
```

The MCP service runs separately from the main API and communicates with it through `CommerceClient`.

---

# Development Principles

When adding a new capability, keep the dependency direction:

```text
New Commerce Capability
          │
          ▼
    FastAPI Backend
       /       \
      /         \
     ▼           ▼
Internal Agent   MCP Server
```

rather than implementing business logic independently in every interface.

For example, if a new commerce operation is required:

1. Implement the operation in the backend.
2. Expose it through the API.
3. Add an agent tool if the internal agent should use it.
4. Add an MCP tool if external agents should use it.
5. Test the backend behaviour and relevant agent/MCP path.

This keeps the backend as the single source of truth.

---

# Design Principles

### One commerce authority

Products, carts, orders, users, and payments are owned by the backend.

### AI is not the source of truth

The LLM proposes actions; application code validates and executes them.

### Agents use capabilities, not internals

The agent interacts through tools and the commerce API instead of directly accessing application state.

### MCP does not duplicate the backend

MCP provides a standard external interface to existing commerce capabilities.

### Identity follows the request

External OAuth identity is mapped to an application user before accessing protected backend operations.

### Payments remain deterministic

Payment state comes from the backend and Razorpay, not from model output.

### Keep the AI layer replaceable

The commerce system should continue to function independently of a particular LLM or agent implementation.

---

# What This Project Demonstrates

This project explores a shift from:

```text
Traditional E-commerce

User → Web App → REST API
```

to:

```text
Agentic E-commerce

Human ──────────────┐
                    │
Internal AI Agent ──┼──► Commerce API ──► State
                    │
External AI ── MCP ─┘
```

The result is not simply a chatbot placed on top of an online store.

It is a **commerce system designed to be operated by agents** while keeping the parts that require determinism — authentication, authorization, state, orders, and payments — inside the application layer.

### The core idea

> **One commerce backend. Multiple interfaces. AI for reasoning, application code for control.**

---

# Contributing

Contributions are welcome.

Before adding functionality, identify which layer owns the responsibility:

```text
Reasoning / intent       → Agent
Tool interface           → Agent Tools / MCP
Business rules           → FastAPI
Persistence              → Database
Payment state            → Razorpay + Backend
Authentication           → Security / WorkOS
```

Keep business logic centralized in the backend and expose it to new interfaces rather than duplicating it.
