import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend, FilesystemBackend
from langchain_core.tools import tool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from typing import Literal

# Load environment variables from .env file
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
SA_KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH")
POSTGRES_URL = os.getenv("DB_CONN")

def get_model():
    """
    Initialize the ChatGoogleGenerativeAI model configured for Vertex AI.
    """
    credentials = None
    if SA_KEY_PATH and os.path.exists(SA_KEY_PATH):
        credentials = service_account.Credentials.from_service_account_file(
            SA_KEY_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )

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
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        search = TavilySearchResults(max_results=max_results)
        return search.invoke(query)
    except ImportError:
        return f"[MOCK SEARCH RESULTS FOR: {query}] - tavily-python or langchain-community not installed."

def get_system_prompt():
    """Load the system prompt from the design-docs directory."""
    # Use absolute path to ensure it works regardless of CWD
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "design-docs", "system_prompt.md")
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read system prompt from {prompt_path}: {e}")
        return "You are an expert, outcome-oriented autonomous AI Design Agent."


def get_backend_factory():
    """Return a backend factory for the CompositeBackend."""
    def backend_factory(rt):
        return CompositeBackend(
            default=FilesystemBackend(root_dir=".", virtual_mode=True),
            routes={
                "/workspace/": StateBackend(rt),
                "/memories/": StoreBackend(rt)
            }
        )
    return backend_factory



def create_agent_with_persistence():
    """
    Create the Deep Agent with all configured backends.
    
    Returns a tuple of (agent, checkpointer, store) so callers can manage
    the lifecycle of persistence resources.
    
    For PostgreSQL mode, the caller is responsible for closing the
    checkpointer and store (they are context managers).
    For in-memory mode, no cleanup is needed.
    """
    if not PROJECT_ID:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT environment variable not set. "
            "Please check your .env file or environment variables."
        )

    llm = get_model()
    system_prompt = get_system_prompt()
    tools = [web_search]
    backend_factory = get_backend_factory()

    if POSTGRES_URL:
        print("Using PostgreSQL for persistence and memory...")
        # from_conn_string returns a context manager
        checkpointer_cm = PostgresSaver.from_conn_string(POSTGRES_URL)
        store_cm = PostgresStore.from_conn_string(POSTGRES_URL)
        
        # Enter context managers to get the actual instances
        checkpointer = checkpointer_cm.__enter__()
        store = store_cm.__enter__()
        
        # Ensure database tables exist
        checkpointer.setup()
        store.setup()
    else:
        print("Warning: DB_CONN not set. Running with in-memory persistence.")
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.store.memory import InMemoryStore
        
        checkpointer = MemorySaver()
        store = InMemoryStore()

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        store=store,
        backend=backend_factory,
        skills=["./design-skills/"]
    )


    return agent, checkpointer, store


def main():
    try:
        agent, checkpointer, store = create_agent_with_persistence()
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"Initializing Gemini 3.0 Flash on Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})...")
    run_agent_demo(agent)

def run_agent_demo(agent):
    """ Helper to run a demo conversation with the agent. """
    # Configuration for persistence (thread-based context)
    config = {"configurable": {"thread_id": "ux-design-session-1"}}
    
    print("Agent is ready. Initiating UX process...")
    
    # Invoke the agent with a sample task
    result = agent.invoke({
        "messages": [{"role": "user", "content": "I want to build a new app for freelance dog walkers to manage their schedules and payments. Please initiate the UX design process. Keep your response brief, we can dig into it in the next step."}]
    }, config=config)
    
    print("\n--- Agent Response ---")
    print(result["messages"][-1].content)

if __name__ == "__main__":
    main()
