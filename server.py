"""
FastAPI server for the Harness Agent.

Serves the Deep Agent over HTTP with:
- POST /chat          — Send a message, receive full response
- POST /stream        — Send a message, receive SSE stream of events
- GET  /threads/{id}/history — Retrieve conversation history
- GET  /health        — Health check

Run with:
    python server.py
    # or
    uvicorn server:app --reload --port 8000
"""

import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import create_agent_with_persistence


# ---------------------------------------------------------------------------
# Global agent state — initialized on startup
# ---------------------------------------------------------------------------
_agent = None
_checkpointer = None
_store = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agent on startup, clean up on shutdown."""
    global _agent, _checkpointer, _store
    print("Starting Harness Agent server...")
    _agent, _checkpointer, _store = create_agent_with_persistence()
    print("Agent initialized successfully.")
    yield
    # Cleanup persistence resources if they support it
    for resource in (_checkpointer, _store):
        if hasattr(resource, "close"):
            try:
                resource.close()
            except Exception:
                pass
    print("Server shut down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Harness Agent API",
    description="HTTP API for the Deep Agent with SSE streaming support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow common local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str = Field(
        ...,
        description="The role of the message sender: 'user' or 'assistant'",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="The text content of the message",
        examples=["Design a mobile app for dog walkers"],
    )


class ChatRequest(BaseModel):
    """Request body for /chat and /stream endpoints."""
    message: str = Field(
        ...,
        description="The user message to send to the agent",
        examples=["I want to build an app for freelance dog walkers"],
    )
    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation thread ID. If omitted, a new UUID is generated. "
            "Reuse the same thread_id to continue a conversation."
        ),
        examples=["ux-session-abc123"],
    )


class ChatResponse(BaseModel):
    """Response body for /chat endpoint."""
    thread_id: str = Field(
        ...,
        description="The thread ID used for this conversation",
    )
    response: str = Field(
        ...,
        description="The agent's text response",
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Unique ID of the response message",
    )


class HistoryMessage(BaseModel):
    """A message in the conversation history."""
    role: str
    content: str
    message_id: Optional[str] = None


class HistoryResponse(BaseModel):
    """Response body for /threads/{thread_id}/history."""
    thread_id: str
    messages: list[HistoryMessage]


class HealthResponse(BaseModel):
    """Response body for /health."""
    status: str
    agent_loaded: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_message_content(content) -> str:
    """Extract text from various LangChain message content formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Content can be a list of blocks (text, image, etc.)
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _make_config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the server and agent are ready."""
    return HealthResponse(
        status="ok",
        agent_loaded=_agent is not None,
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to the agent and receive the full response.

    This endpoint invokes the agent synchronously and waits for the
    complete response before returning. Use `/stream` for real-time
    token-by-token output.
    """
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = request.thread_id or str(uuid.uuid4())
    config = _make_config(thread_id)

    # Run the agent invocation in a thread pool to avoid blocking the event loop
    result = await asyncio.to_thread(
        _agent.invoke,
        {"messages": [{"role": "user", "content": request.message}]},
        config,
    )

    # Extract the last AI message
    last_message = result["messages"][-1]
    response_text = _serialize_message_content(last_message.content)

    return ChatResponse(
        thread_id=thread_id,
        response=response_text,
        message_id=getattr(last_message, "id", None),
    )


@app.post("/stream", tags=["Chat"])
async def stream(request: ChatRequest):
    """
    Send a message to the agent and receive an SSE event stream.

    Uses LangGraph's v2 streaming format with subgraph streaming enabled.
    Each SSE event is a JSON object with `type`, `ns`, and `data` keys.

    **Event types:**
    - `updates` — step completions (node transitions)
    - `messages` — LLM token chunks (token-by-token streaming)
    - `custom` — user-defined progress events from tools

    **Namespace (`ns`):**
    - `[]` (empty) — event from the main agent
    - `["tools:<id>"]` — event from a subagent with the given tool call ID
    """
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    thread_id = request.thread_id or str(uuid.uuid4())
    config = _make_config(thread_id)

    async def event_generator():
        """Generate SSE events from the agent stream."""
        # Send the thread_id as the first event so the client knows it
        yield _sse_encode("metadata", {"thread_id": thread_id})

        # Run the streaming in a thread pool since the agent uses sync APIs
        def _stream_sync():
            return list(
                _agent.stream(
                    {"messages": [{"role": "user", "content": request.message}]},
                    config=config,
                    stream_mode=["updates", "messages"],
                    subgraphs=True,
                    version="v2",
                )
            )

        chunks = await asyncio.to_thread(_stream_sync)

        for chunk in chunks:
            event_type = chunk.get("type", "unknown")
            ns = list(chunk.get("ns", ()))
            data = chunk.get("data", {})

            # Process based on event type
            if event_type == "updates":
                for node_name, node_data in data.items():
                    # Extract messages from the update
                    messages_data = []
                    for msg in node_data.get("messages", []):
                        messages_data.append({
                            "type": getattr(msg, "type", "unknown"),
                            "content": _serialize_message_content(
                                getattr(msg, "content", "")
                            ),
                            "id": getattr(msg, "id", None),
                            "tool_calls": [
                                {
                                    "id": tc.get("id"),
                                    "name": tc.get("name"),
                                    "args": tc.get("args", {}),
                                }
                                for tc in getattr(msg, "tool_calls", [])
                            ],
                        })

                    event_payload = {
                        "node": node_name,
                        "ns": ns,
                        "messages": messages_data,
                    }
                    yield _sse_encode("update", event_payload)

            elif event_type == "messages":
                token, metadata = data
                token_content = _serialize_message_content(
                    getattr(token, "content", "")
                )
                tool_call_chunks = []
                for tc in getattr(token, "tool_call_chunks", []) or []:
                    tool_call_chunks.append({
                        "name": tc.get("name"),
                        "args": tc.get("args"),
                        "id": tc.get("id"),
                    })

                if token_content or tool_call_chunks:
                    event_payload = {
                        "ns": ns,
                        "content": token_content,
                        "type": getattr(token, "type", "unknown"),
                        "message_id": getattr(token, "id", None),
                        "tool_call_chunks": tool_call_chunks if tool_call_chunks else None,
                    }
                    yield _sse_encode("token", event_payload)

            elif event_type == "custom":
                event_payload = {
                    "ns": ns,
                    "data": data,
                }
                yield _sse_encode("custom", event_payload)

        # Signal the stream is complete
        yield _sse_encode("done", {"thread_id": thread_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_encode(event_type: str, data: dict) -> str:
    """Format a dict as an SSE event string."""
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"


@app.get(
    "/threads/{thread_id}/history",
    response_model=HistoryResponse,
    tags=["Threads"],
)
async def get_thread_history(thread_id: str):
    """
    Retrieve the conversation history for a given thread.

    Returns all messages in the thread in chronological order.
    """
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    config = _make_config(thread_id)

    try:
        state = await asyncio.to_thread(_agent.get_state, config)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Thread '{thread_id}' not found or has no state: {e}",
        )

    if not state or not state.values:
        raise HTTPException(
            status_code=404,
            detail=f"Thread '{thread_id}' not found or has no messages",
        )

    messages = []
    for msg in state.values.get("messages", []):
        messages.append(
            HistoryMessage(
                role=getattr(msg, "type", "unknown"),
                content=_serialize_message_content(getattr(msg, "content", "")),
                message_id=getattr(msg, "id", None),
            )
        )

    return HistoryResponse(thread_id=thread_id, messages=messages)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
