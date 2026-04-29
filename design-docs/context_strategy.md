# Autonomous AI Harness: Context Strategy

This document outlines the context engineering strategy for the autonomous AI agent harness. It is designed for a single main agent executing a rapid MVP UX process, utilizing LangChain's **Deep Agents** framework. The strategy relies on dynamic memory injection, skill-based progressive disclosure, and robust context compression to ensure the LLM's context window remains focused and efficient.

## 1. Single Main Agent Architecture

The harness employs a single main agent rather than a multi-agent (subagent) setup. The four core UX capabilities (`problem-and-hypothesis-analyzer`, `risk-reward-evaluator`, `mvp-core-architect`, `ai-coder-prompt-engineer`) are implemented as **Skills**.

This approach minimizes communication overhead. The single main agent selectively loads the specific skill required for the current phase of the MVP lifecycle, keeping the context clean.

## 2. Input Context Components

The agent's context window is primarily composed of the following inputs provided at startup:

### System Prompt
The static base instructions defining the agent's role as an autonomous MVP developer. It provides overarching guidance on prioritizing live-code MVPs over traditional UX artifacts and utilizing the available skills and memory.

### Memory (Persistent Context)
Memory files that are *always* loaded into the system prompt. For this harness, these are files from our persistent store (routed via `CompositeBackend`), such as:
*   `/memories/harness_preferences.md`: Developer preferences, tech stack constraints.
*   `/memories/current_project_context.md`: The active project's problem statement and hypotheses.

*Guideline:* Keep these files extremely concise. Detailed historical data (like past hypotheses) should *not* be loaded here automatically to avoid context bloat.

### Skills (Progressive Disclosure)
The four core UX skills are provided via the `skills` parameter pointing to a local directory (e.g., `skills=["/skills/"]`).
*   **Progressive Disclosure:** Deep Agents automatically read only the YAML frontmatter (description and name) of each `SKILL.md` file at startup. The full content of a skill (e.g., the specific instructions for the `risk-reward-evaluator`) is only loaded into the prompt when the agent determines that skill is needed for the current task.
*   *Guideline:* Ensure the descriptions in the YAML frontmatter of each skill are highly descriptive to help the main agent accurately determine when to load them.

## 3. Managing Dynamic State (No Runtime Context)

We explicitly avoid passing dynamic configuration via the `runtime context` at invocation. All required operational knowledge is derived from the persistent memory (`/memories/`) or ephemeral workspace (`/workspace/`) using the configured `CompositeBackend` (as detailed in `memory_system_design.md`).

## 4. Context Compression and Offloading Guidelines

Because the harness operates as a single agent through a multi-step UX process, the conversation history and tool outputs will grow significantly. To prevent exceeding the model's context limits, we rely on Deep Agents' built-in compression mechanisms.

### Automatic Tool Output Offloading
*   **Mechanism:** Deep Agents automatically offload tool inputs or outputs that exceed the token threshold (default ~20,000 tokens) to the filesystem. The large content is replaced in the context window with a file path reference and a brief preview.
*   **Application:** When the agent generates a massive `final_prompt.md` or reads the extensive `/memories/hypotheses_log.md`, the raw text won't clog the active context. The agent can use filesystem tools (`grep`, `read_file` with limits) to selectively query this offloaded data.

### Conversation Summarization
*   **Mechanism:** When the conversation history approaches 85% of the model's context window limit, the agent triggers an automatic summarization.
*   **Application:** Older turns—such as the early brainstorming from the `problem-and-hypothesis-analyzer`—are compressed into a structured LLM-generated summary, while the full canonical history is preserved in the filesystem.
*   *Guideline:* Because summarization loses fine-grained details, the agent must be strictly instructed (via its system prompt and skills) to *always* write critical decisions to the persistent memory files (`/memories/current_project_context.md`) immediately after they are made, ensuring they survive context summarization.

## 5. Storage Strategy Alignment

This context strategy works directly in tandem with the memory design:
*   **Ephemeral `/workspace/`:** Used for intermediate drafts. The agent knows this data might vanish across threads, so it's strictly for short-term working context.
*   **Persistent `/memories/`:** Uses a static `solo-dev-harness` namespace. The agent retrieves context from here globally, but heavily relies on offloading when reading large historical logs like the `hypotheses_log.md`.