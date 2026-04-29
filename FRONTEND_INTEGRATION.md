# Frontend Integration Guide — Harness Agent API

This document explains how your frontend should interact with the Harness Agent FastAPI server. It covers every endpoint, the exact request/response formats, the SSE streaming protocol, and patterns for building real-time UIs with React, Vue, Svelte, or vanilla JavaScript.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
   - [GET /health](#get-health)
   - [POST /chat](#post-chat)
   - [POST /stream](#post-stream)
   - [GET /threads/{thread_id}/history](#get-threadsthread_idhistory)
4. [SSE Streaming Protocol](#sse-streaming-protocol)
   - [Event Types](#event-types)
   - [Namespace Routing (Subagents)](#namespace-routing-subagents)
   - [Full Event Flow Example](#full-event-flow-example)
5. [Frontend Patterns](#frontend-patterns)
   - [Vanilla JavaScript (fetch + EventSource)](#vanilla-javascript)
   - [React with useStream](#react-with-usestream)
   - [Subagent Card Rendering](#subagent-card-rendering)
   - [Todo List / Progress Tracking](#todo-list--progress-tracking)
6. [Error Handling](#error-handling)
7. [Configuration](#configuration)

---

## Architecture Overview

The Harness Agent uses a **coordinator-worker architecture**. The main agent plans tasks and can delegate to specialized subagents, each running in isolation.

```
┌─────────────┐         ┌──────────────────┐
│   Frontend   │◄──SSE──►│  FastAPI Server   │
│  (Browser)   │         │   (server.py)     │
└─────────────┘         └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │   Deep Agent      │
                        │  (Coordinator)    │
                        └──┬──────────┬────┘
                           │          │
                    ┌──────▼──┐  ┌───▼───────┐
                    │Subagent │  │ Subagent   │
                    │   A     │  │    B       │
                    └─────────┘  └───────────┘
```

**Key concepts:**
- **Thread** — a single conversation. State (messages, todos, files) is scoped to a thread.
- **Thread ID** — a unique string identifying a conversation. Reuse it to continue a conversation.
- **Subagent** — a specialist agent spawned by the coordinator to handle a specific task.

---

## Quick Start

1. **Start the server:**
   ```bash
   python server.py
   # Server runs at http://localhost:8000
   # Swagger docs at http://localhost:8000/docs
   ```

2. **Send a message:**
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Design a mobile app for dog walkers"}'
   ```

3. **Stream a response:**
   ```bash
   curl -N -X POST http://localhost:8000/stream \
     -H "Content-Type: application/json" \
     -d '{"message": "Design a mobile app for dog walkers"}'
   ```

---

## API Endpoints

### `GET /health`

Check if the server and agent are ready.

**Request:**
```
GET /health
```

No request body required.

**Response:** `200 OK`
```json
{
  "status": "ok",
  "agent_loaded": true
}
```

**Response fields:**

| Field          | Type    | Description                           |
|----------------|---------|---------------------------------------|
| `status`       | string  | Always `"ok"` if the server is up     |
| `agent_loaded` | boolean | `true` if the agent is initialized    |

---

### `POST /chat`

Send a message and receive the **complete** response. The server waits for the agent to finish processing before responding. Use this when you don't need real-time streaming.

**Request:**
```
POST /chat
Content-Type: application/json
```

**Request body:**
```json
{
  "message": "I want to build an app for freelance dog walkers",
  "thread_id": "ux-session-abc123"
}
```

**Request fields:**

| Field       | Type            | Required | Description                                                                              |
|-------------|-----------------|----------|------------------------------------------------------------------------------------------|
| `message`   | string          | ✅ Yes    | The user's message to send to the agent                                                  |
| `thread_id` | string \| null  | ❌ No     | Conversation thread ID. If omitted, a new UUID is generated. Reuse to continue a thread. |

**Response:** `200 OK`
```json
{
  "thread_id": "ux-session-abc123",
  "response": "Great! Let me start by understanding the core problem...",
  "message_id": "run-abc123-msg-001"
}
```

**Response fields:**

| Field        | Type           | Description                                  |
|--------------|----------------|----------------------------------------------|
| `thread_id`  | string         | The thread ID used (either yours or generated)|
| `response`   | string         | The agent's complete text response            |
| `message_id` | string \| null | Unique identifier for this response message   |

**Example (JavaScript):**
```javascript
const response = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "Design a mobile app for dog walkers",
    thread_id: "my-session-1",
  }),
});

const data = await response.json();
console.log(data.response);    // Agent's full response
console.log(data.thread_id);   // "my-session-1"
```

---

### `POST /stream`

Send a message and receive a **Server-Sent Events (SSE)** stream of real-time updates. This is the recommended endpoint for interactive UIs.

**Request:**
```
POST /stream
Content-Type: application/json
```

**Request body:** *(identical to /chat)*
```json
{
  "message": "I want to build an app for freelance dog walkers",
  "thread_id": "ux-session-abc123"
}
```

**Request fields:**

| Field       | Type            | Required | Description                                                                              |
|-------------|-----------------|----------|------------------------------------------------------------------------------------------|
| `message`   | string          | ✅ Yes    | The user's message to send to the agent                                                  |
| `thread_id` | string \| null  | ❌ No     | Conversation thread ID. If omitted, a new UUID is generated. Reuse to continue a thread. |

**Response:** `200 OK` with `Content-Type: text/event-stream`

The response is an SSE stream. Each event follows this format:
```
event: <event_type>
data: <json_payload>

```

See [SSE Streaming Protocol](#sse-streaming-protocol) for the full event specification.

---

### `GET /threads/{thread_id}/history`

Retrieve the full conversation history for a thread.

**Request:**
```
GET /threads/ux-session-abc123/history
```

**Path parameters:**

| Parameter    | Type   | Description                    |
|--------------|--------|--------------------------------|
| `thread_id`  | string | The conversation thread ID     |

**Response:** `200 OK`
```json
{
  "thread_id": "ux-session-abc123",
  "messages": [
    {
      "role": "human",
      "content": "Design a mobile app for dog walkers",
      "message_id": "msg-001"
    },
    {
      "role": "ai",
      "content": "Great! Let me start by understanding the core problem...",
      "message_id": "msg-002"
    }
  ]
}
```

**Response fields:**

| Field        | Type   | Description                                 |
|--------------|--------|---------------------------------------------|
| `thread_id`  | string | The thread ID                               |
| `messages`   | array  | Chronologically ordered list of messages    |

**Each message in the array:**

| Field        | Type           | Description                                     |
|--------------|----------------|-------------------------------------------------|
| `role`       | string         | `"human"` for user messages, `"ai"` for agent   |
| `content`    | string         | The text content of the message                  |
| `message_id` | string \| null | Unique identifier for this message               |

**Error:** `404 Not Found`
```json
{
  "detail": "Thread 'nonexistent-id' not found or has no messages"
}
```

---

## SSE Streaming Protocol

When using `POST /stream`, the server sends a sequence of SSE events. The stream always starts with a `metadata` event and ends with a `done` event.

### Event Types

#### 1. `metadata` — Stream initialization

Sent as the **first event**. Contains the thread ID.

```
event: metadata
data: {"thread_id": "ux-session-abc123"}
```

| Field       | Type   | Description                   |
|-------------|--------|-------------------------------|
| `thread_id` | string | The thread ID for this stream |

---

#### 2. `update` — Agent step completion

Sent when the agent completes a processing step (e.g., model inference, tool execution).

```
event: update
data: {"node": "model_request", "ns": [], "messages": [...]}
```

| Field      | Type   | Description                                                              |
|------------|--------|--------------------------------------------------------------------------|
| `node`     | string | The graph node that completed: `"model_request"`, `"tools"`, etc.        |
| `ns`       | array  | Namespace path. `[]` = main agent. `["tools:<id>"]` = subagent.          |
| `messages` | array  | Messages produced by this step                                           |

**Each message in the `messages` array:**

| Field         | Type           | Description                                           |
|---------------|----------------|-------------------------------------------------------|
| `type`        | string         | Message type: `"ai"`, `"tool"`, `"human"`             |
| `content`     | string         | The text content                                       |
| `id`          | string \| null | Message unique ID                                      |
| `tool_calls`  | array          | Tool calls made by this message (if any)               |

**Each tool call:**

| Field  | Type   | Description                                      |
|--------|--------|--------------------------------------------------|
| `id`   | string | Tool call ID                                     |
| `name` | string | Tool name (e.g., `"web_search"`, `"task"`)       |
| `args` | object | Arguments passed to the tool                     |

---

#### 3. `token` — LLM token chunk

Sent for each token (or small batch of tokens) as the LLM generates text. This is how you implement typewriter-style streaming.

```
event: token
data: {"ns": [], "content": "Great", "type": "ai", "message_id": "msg-001", "tool_call_chunks": null}
```

| Field               | Type           | Description                                               |
|---------------------|----------------|-----------------------------------------------------------|
| `ns`                | array          | Namespace. `[]` = main agent, `["tools:<id>"]` = subagent |
| `content`           | string         | The token text (may be empty if this is a tool call chunk) |
| `type`              | string         | Usually `"ai"` for model-generated tokens                  |
| `message_id`        | string \| null | ID of the message being streamed                           |
| `tool_call_chunks`  | array \| null  | Tool call fragments being streamed (if any)                |

**Each tool call chunk (when present):**

| Field  | Type           | Description                                           |
|--------|----------------|-------------------------------------------------------|
| `name` | string \| null | Tool name (present on the first chunk of a tool call) |
| `args` | string \| null | JSON fragment of arguments (streamed incrementally)   |
| `id`   | string \| null | Tool call ID (present on the first chunk)             |

---

#### 4. `custom` — Custom progress events

Sent when agent tools emit custom updates via `get_stream_writer()`.

```
event: custom
data: {"ns": ["tools:call_abc123"], "data": {"status": "analyzing", "progress": 50}}
```

| Field  | Type   | Description                                                   |
|--------|--------|---------------------------------------------------------------|
| `ns`   | array  | Namespace identifying which agent/tool emitted the event      |
| `data` | object | Arbitrary payload defined by the tool                         |

---

#### 5. `done` — Stream complete

Sent as the **last event**. Signals the stream is finished.

```
event: done
data: {"thread_id": "ux-session-abc123"}
```

---

### Namespace Routing (Subagents)

The `ns` (namespace) array tells you which agent produced an event:

| `ns` value             | Source                                              |
|------------------------|-----------------------------------------------------|
| `[]`                   | Main agent (coordinator)                            |
| `["tools:<id>"]`       | Subagent spawned by tool call `<id>`                |
| `["tools:<id>", ...]`  | Deeper nesting (subagent's own tool call)           |

**How to check if an event is from a subagent:**
```javascript
const isSubagent = event.ns.some(s => s.startsWith("tools:"));
```

**How to extract the subagent's tool call ID:**
```javascript
const toolCallId = event.ns.find(s => s.startsWith("tools:"))?.split(":")[1];
```

---

### Full Event Flow Example

Here's a typical stream for a message that triggers a subagent:

```
event: metadata
data: {"thread_id": "session-123"}

event: update
data: {"node": "model_request", "ns": [], "messages": [{"type": "ai", "content": "", "id": "msg-1", "tool_calls": [{"id": "call_abc", "name": "task", "args": {"subagent_type": "researcher", "description": "Research dog walker market"}}]}]}

event: token
data: {"ns": ["tools:call_abc"], "content": "Based on my", "type": "ai", "message_id": "msg-2", "tool_call_chunks": null}

event: token
data: {"ns": ["tools:call_abc"], "content": " research,", "type": "ai", "message_id": "msg-2", "tool_call_chunks": null}

event: token
data: {"ns": ["tools:call_abc"], "content": " the dog walking", "type": "ai", "message_id": "msg-2", "tool_call_chunks": null}

event: update
data: {"node": "tools", "ns": [], "messages": [{"type": "tool", "content": "Research complete: ...", "id": "msg-3", "tool_calls": []}]}

event: token
data: {"ns": [], "content": "Based on the research", "type": "ai", "message_id": "msg-4", "tool_call_chunks": null}

event: token
data: {"ns": [], "content": " findings, here is my recommendation...", "type": "ai", "message_id": "msg-4", "tool_call_chunks": null}

event: update
data: {"node": "model_request", "ns": [], "messages": [{"type": "ai", "content": "Based on the research findings, here is my recommendation...", "id": "msg-4", "tool_calls": []}]}

event: done
data: {"thread_id": "session-123"}
```

---

## Frontend Patterns

### Vanilla JavaScript

#### Using `fetch` with `ReadableStream` (recommended for POST SSE)

Since `/stream` is a POST endpoint, you can't use `EventSource` (which only supports GET). Use `fetch` with a readable stream instead:

```javascript
async function streamChat(message, threadId = null) {
  const response = await fetch("http://localhost:8000/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message,
      thread_id: threadId,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentThreadId = threadId;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from the buffer
    const events = buffer.split("\n\n");
    buffer = events.pop(); // Keep incomplete event in buffer

    for (const eventStr of events) {
      if (!eventStr.trim()) continue;

      const lines = eventStr.split("\n");
      let eventType = "";
      let eventData = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7);
        } else if (line.startsWith("data: ")) {
          eventData = line.slice(6);
        }
      }

      if (!eventType || !eventData) continue;

      const data = JSON.parse(eventData);

      switch (eventType) {
        case "metadata":
          currentThreadId = data.thread_id;
          console.log("Stream started, thread:", currentThreadId);
          break;

        case "token":
          // Check if this is from the main agent or a subagent
          const isSubagent = data.ns.some((s) => s.startsWith("tools:"));
          if (data.content) {
            if (isSubagent) {
              // Append to subagent display
              appendToSubagent(data.ns, data.content);
            } else {
              // Append to main response display
              appendToResponse(data.content);
            }
          }
          break;

        case "update":
          console.log(`Step completed: ${data.node}`, data.ns);
          // Check for tool calls (subagent spawning)
          for (const msg of data.messages) {
            for (const tc of msg.tool_calls) {
              if (tc.name === "task") {
                onSubagentSpawned(tc.id, tc.args);
              }
            }
          }
          break;

        case "custom":
          console.log("Custom event:", data.data);
          break;

        case "done":
          console.log("Stream complete");
          break;
      }
    }
  }

  return currentThreadId;
}

// Helper: append text to the main response area
function appendToResponse(text) {
  const el = document.getElementById("response");
  el.textContent += text;
}

// Helper: append text to a subagent's display area
function appendToSubagent(ns, text) {
  const subagentId = ns.find((s) => s.startsWith("tools:"));
  let el = document.getElementById(`subagent-${subagentId}`);
  if (!el) {
    el = document.createElement("div");
    el.id = `subagent-${subagentId}`;
    el.className = "subagent-card";
    document.getElementById("subagents").appendChild(el);
  }
  el.textContent += text;
}

// Helper: handle subagent spawn
function onSubagentSpawned(toolCallId, args) {
  console.log(`Subagent spawned: ${args.subagent_type} — ${args.description}`);
}
```

#### Continuing a Conversation

```javascript
// First message — no thread_id, one is generated
const threadId = await streamChat("Design a mobile app for dog walkers");

// Follow-up — reuse the thread_id
await streamChat("Focus on the payment flow", threadId);

// Another follow-up in the same thread
await streamChat("Add support for recurring appointments", threadId);
```

#### Fetching History

```javascript
async function getHistory(threadId) {
  const response = await fetch(
    `http://localhost:8000/threads/${threadId}/history`
  );
  const data = await response.json();

  for (const msg of data.messages) {
    console.log(`[${msg.role}]: ${msg.content}`);
  }
}
```

---

### React with `useStream`

If your frontend uses LangChain's `@langchain/react` package, you can use the `useStream` hook for a higher-level integration. This works with the LangGraph Agent Protocol server (port 2024). For the custom FastAPI server described here, use the vanilla fetch approach above or adapt `useStream` to point at your endpoints.

> **Note:** `useStream` expects the LangGraph Agent Protocol API shape (provided by `langgraph dev` or LangSmith Deployments). The FastAPI server in this project uses a compatible but simplified API. For full `useStream` compatibility, consider running `langgraph dev` alongside or instead of the custom FastAPI server.

```tsx
import { useStream } from "@langchain/react";

const AGENT_URL = "http://localhost:2024"; // LangGraph dev server

function App() {
  const stream = useStream({
    apiUrl: AGENT_URL,
    assistantId: "agent",
    filterSubagentMessages: true, // Separate coordinator from subagent tokens
  });

  return (
    <div>
      {/* Coordinator messages */}
      {stream.messages.map((msg) => (
        <MessageWithSubagents
          key={msg.id}
          message={msg}
          subagents={stream.getSubagentsByMessage(msg.id)}
        />
      ))}

      {/* Chat input */}
      <input
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            stream.submit(
              { messages: [{ type: "human", content: e.target.value }] },
              { streamSubgraphs: true }
            );
          }
        }}
      />
    </div>
  );
}
```

---

### Subagent Card Rendering

When the agent delegates work to subagents, you can render each subagent's progress as a collapsible card. Track subagent lifecycle from the `update` events:

```javascript
const subagents = new Map();

function handleUpdateEvent(data) {
  // Detect subagent spawning (main agent calls 'task' tool)
  if (data.ns.length === 0 && data.node === "model_request") {
    for (const msg of data.messages) {
      for (const tc of msg.tool_calls) {
        if (tc.name === "task") {
          subagents.set(tc.id, {
            id: tc.id,
            type: tc.args.subagent_type,
            description: tc.args.description,
            status: "pending",
            content: "",
            startedAt: null,
            completedAt: null,
          });
          renderSubagentCard(tc.id);
        }
      }
    }
  }

  // Detect subagent completion (tool message returns)
  if (data.ns.length === 0 && data.node === "tools") {
    for (const msg of data.messages) {
      if (msg.type === "tool") {
        const sub = subagents.get(msg.id);
        if (sub) {
          sub.status = "complete";
          sub.completedAt = Date.now();
          sub.content = msg.content;
          renderSubagentCard(msg.id);
        }
      }
    }
  }
}

function handleTokenEvent(data) {
  if (data.ns.length > 0) {
    // Token from a subagent — mark as running and accumulate content
    const toolCallId = data.ns
      .find((s) => s.startsWith("tools:"))
      ?.split(":")[1];

    // Find matching subagent (ns IDs may differ from tool_call IDs)
    for (const [id, sub] of subagents) {
      if (sub.status === "pending") {
        sub.status = "running";
        sub.startedAt = Date.now();
        break;
      }
    }

    // Append content to the running subagent
    for (const [id, sub] of subagents) {
      if (sub.status === "running" && data.content) {
        sub.content += data.content;
        renderSubagentCard(id);
        break;
      }
    }
  }
}
```

---

### Todo List / Progress Tracking

The agent uses a `todos` state key to track multi-step plans. These appear in `update` events when the agent writes todos. You can access them from the state:

**Extracting todos from stream events:**
```javascript
let todos = [];

function handleUpdateEvent(data) {
  // Check if the update contains todos
  for (const msg of data.messages) {
    // Look for write_todos tool calls
    for (const tc of msg.tool_calls) {
      if (tc.name === "write_todos" && tc.args.todos) {
        todos = tc.args.todos;
        renderTodoList(todos);
      }
    }
  }
}

function renderTodoList(todos) {
  const container = document.getElementById("todo-list");
  container.innerHTML = "";

  const completed = todos.filter((t) => t.status === "completed").length;
  const percentage = Math.round((completed / todos.length) * 100);

  // Progress bar
  container.innerHTML += `
    <div class="progress-bar">
      <div class="fill" style="width: ${percentage}%"></div>
      <span>${completed}/${todos.length} tasks (${percentage}%)</span>
    </div>
  `;

  // Todo items
  for (const todo of todos) {
    const icon =
      todo.status === "completed"
        ? "✓"
        : todo.status === "in_progress"
          ? "◉"
          : "○";
    const cls = `todo-item todo-${todo.status}`;
    container.innerHTML += `<div class="${cls}">${icon} ${todo.content}</div>`;
  }
}
```

**Fetching current todos from thread state:**
```javascript
async function getTodos(threadId) {
  const response = await fetch(
    `http://localhost:8000/threads/${threadId}/history`
  );
  const data = await response.json();

  // Parse todos from the latest write_todos tool call in history
  for (const msg of data.messages.reverse()) {
    if (msg.role === "ai" && msg.content.includes("write_todos")) {
      // Extract todos from the tool call
      break;
    }
  }
}
```

---

## Error Handling

### HTTP Error Responses

All error responses use standard HTTP status codes with a JSON body:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning                                | When                                         |
|--------|----------------------------------------|----------------------------------------------|
| `400`  | Bad Request                            | Invalid request body (missing `message`, etc.)|
| `404`  | Not Found                              | Thread ID doesn't exist                       |
| `422`  | Unprocessable Entity                   | Request body validation failed                |
| `503`  | Service Unavailable                    | Agent not yet initialized                     |

### Stream Error Handling

If an error occurs during streaming, the stream may end prematurely without a `done` event. Always implement a timeout:

```javascript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 120_000); // 2 min timeout

try {
  const response = await fetch("http://localhost:8000/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "...", thread_id: "..." }),
    signal: controller.signal,
  });
  // ... process stream
} catch (err) {
  if (err.name === "AbortError") {
    console.error("Stream timed out");
  }
} finally {
  clearTimeout(timeout);
}
```

---

## Configuration

### Server URL

The default server URL is `http://localhost:8000`. Update this in your frontend config based on your deployment:

```javascript
// Development
const API_URL = "http://localhost:8000";

// Production
const API_URL = "https://your-api-domain.com";
```

### CORS

The server allows requests from these origins by default:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://localhost:8080`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:8080`

To add more origins, edit the `allow_origins` list in `server.py`.

### Thread Management

- **New conversation:** omit `thread_id` or set it to `null`. The server generates a UUID.
- **Continue conversation:** pass the `thread_id` returned by a previous call.
- **Multiple conversations:** use different `thread_id` values for each conversation.

```javascript
// Store thread IDs per conversation
const conversations = {};

async function startNewChat(topic) {
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: `Let's discuss: ${topic}` }),
  });
  const data = await res.json();
  conversations[topic] = data.thread_id;
  return data;
}

async function continueChat(topic, message) {
  const threadId = conversations[topic];
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  return await res.json();
}
```

---

## References

- [Deep Agents Streaming](https://docs.langchain.com/oss/python/deepagents/streaming) — v2 streaming format, subgraph streaming, namespaces
- [Deep Agents Frontend Overview](https://docs.langchain.com/oss/python/deepagents/frontend/overview) — `useStream` patterns, subagent cards, todo lists
- [FastAPI Documentation](https://fastapi.tiangolo.com/) — Server framework docs
- [SSE Specification](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) — Server-Sent Events standard
