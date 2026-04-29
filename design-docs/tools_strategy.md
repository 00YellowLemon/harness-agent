# Autonomous AI Harness: Tools Strategy

This document outlines the tools strategy for the single main agent driving the rapid MVP UX process. It aligns directly with the `CompositeBackend` memory system and the progressive disclosure context strategy.

The core philosophy is to **prioritize built-in Deep Agents filesystem tools** for all "backend" interactions (managing state and memory) and only introduce custom tools when external capabilities are required.

## 1. Tool Architecture and Integration

The harness operates as a single main agent leveraging LangChain's Deep Agents framework. Tools are provided to the model through the system prompt via "Tool Prompts".

*   **State and Memory Management:** Handled exclusively by built-in virtual filesystem tools operating on the `/workspace/` (ephemeral) and `/memories/` (persistent) directories.
*   **External Data Gathering:** Handled by specific custom tools (e.g., Web Search) injected into the agent to pull real-world data during the hypothesis and evaluation phases.
*   **Context Engineering:** All tools rely on Deep Agents' built-in context compression. Large tool inputs (like writing massive drafts) or large outputs (like extensive web search results) are automatically offloaded to the filesystem and replaced with file references to protect the LLM's context window.

## 2. Built-in Filesystem Tools (The "Backend")

The agent's "backend" is the memory system. The agent will rely on the following built-in Deep Agents tools to interact with it natively:

### Tool Set
*   `ls` / `glob`: To discover what context files exist in `/memories/` or what drafts are in `/workspace/`.
*   `read_file`: To pull specific context into working memory (e.g., reading `/memories/harness_preferences.md`).
*   `write_file`: To create new drafts or overwrite context (e.g., finalizing `/workspace/final_prompt.md`).
*   `edit_file`: To modify existing files, specifically useful for appending data to episodic memory.
*   `grep`: To search through large logs without loading the entire file into context.

### Usage by Skill
*   **`problem-and-hypothesis-analyzer`**:
    *   Uses `read_file` on `/memories/hypotheses_log.md` to avoid repeating past ideas.
    *   Uses `write_file` to draft `/workspace/current_problem.md`.
    *   Uses `edit_file` to append new hypotheses to `/memories/hypotheses_log.md`.
    *   Uses `write_file` to set `/memories/current_project_context.md`.
*   **`risk-reward-evaluator`**:
    *   Uses `read_file` to ingest `/memories/current_project_context.md`.
    *   Uses `write_file` for intermediate calculations in `/workspace/risk_reward_scratchpad.md`.
    *   Uses `edit_file` to log evaluations into `/memories/hypotheses_log.md`.
*   **`mvp-core-architect`**:
    *   Uses `write_file` to create `/workspace/mvp_core_draft.md`.
*   **`ai-coder-prompt-engineer`**:
    *   Uses `read_file` to compile all necessary workspace drafts and preferences.
    *   Uses `write_file` to generate the ultimate `/workspace/final_prompt.md`. (Note: The process finishes here; no custom tool is used to actively trigger the external coding agent).

## 3. Custom Tools: External Data Gathering

While filesystem tools handle memory, the `problem-and-hypothesis-analyzer` and `risk-reward-evaluator` require real-world grounding to validate pain points, assess market risks, and research competitors.

We introduce a custom `web_search` tool for this purpose.

### Design: `web_search`
This tool will query an external search API (e.g., Tavily, DuckDuckGo) and return results. If the results are too large, Deep Agents will automatically offload them to the ephemeral backend and provide the agent with a file reference.

**Tool Template & Schema:**
```python
from typing import Literal
from langchain.tools import tool

@tool(parse_docstring=True)
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "general",
) -> str:
    """Run an internet web search to gather real-world data.

    Use this tool to research market trends, validate user pain points,
    check competitor features, or assess technical risks.
    If the results are very long, they will be automatically offloaded to your
    workspace, and you will receive a file path to read them using `read_file`.

    Args:
        query: The search query to execute. Be specific.
        max_results: The maximum number of search results to return (default: 5).
        topic: The type of search to run: 'general' for broad web search, 'news' for recent events.
    """
    # Implementation logic to call an external search API goes here
    pass
```

## 4. Context Compression Strategy

To ensure the agent doesn't crash when dealing with large files or massive search results:
*   **Input Offloading:** When the agent uses `write_file` to generate the massive `/workspace/final_prompt.md`, Deep Agents will truncate the tool call in the prompt history, replacing it with a pointer to the file on disk.
*   **Output Offloading:** When `web_search` returns a huge payload, it is offloaded to the filesystem. The agent is notified with a preview (first 10 lines) and the location, allowing it to use `grep` or `read_file` to parse the exact information it needs.
