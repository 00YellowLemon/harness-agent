import os
from dotenv import load_dotenv
from langgraph.store.postgres import PostgresStore
from langgraph.store.memory import InMemoryStore
from deepagents.backends.utils import create_file_data

load_dotenv()

POSTGRES_URL = os.getenv("DB_CONN")

def initialize_memories():
    preferences_content = """# Developer Preferences & Constraints

## Tech Stack
*   **Backend:** Python, FastAPI
*   **AI Framework:** LangChain, LangGraph, Deep Agents
*   **Database:** PostgreSQL (Supabase)
*   **Frontend:** React, Vite (Tailwind CSS)

## Design Principles
*   **MVP First:** Always prioritize the absolute minimal testable core.
*   **Live-Code:** We move to code as quickly as possible.
*   **Outcome-Oriented:** Focus on validating hypotheses.

## Operational Constraints
*   **Project ID:** decisively-post-486313-b1
*   **Location:** global
"""

    if POSTGRES_URL:
        print("Connecting to PostgreSQL store...")
        from langgraph.store.postgres import PostgresStore
        with PostgresStore.from_conn_string(POSTGRES_URL) as store:
            store.setup()
            print("Writing /memories/harness_preferences.md to store...")
            store.put(
                namespace=("filesystem",),
                key="/memories/harness_preferences.md",
                value=create_file_data(preferences_content)
            )
    else:
        print("Using in-memory store...")
        store = InMemoryStore()
        print("Writing /memories/harness_preferences.md to store...")
        store.put(
            namespace=("filesystem",),
            key="/memories/harness_preferences.md",
            value=create_file_data(preferences_content)
        )
    
    print("Initialization complete.")


if __name__ == "__main__":
    initialize_memories()
