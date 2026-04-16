import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

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
        model="gemini-3-flash-preview",
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )

@tool
def get_current_time() -> str:
    """Get the current time from the system.
    
    Returns:
        The current date and time as a string.
    """
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    if not PROJECT_ID:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable not set.")
        print("Please check your .env file or environment variables.")
        return

    print(f"Initializing Gemini 3.0 Flash on Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})...")
    
    llm = get_model()
    
    system_prompt = "You are a simple and helpful assistant using Gemini on Vertex AI. You can use tools if needed."
    tools = [get_current_time]
    
    # Initialize persistence if POSTGRES_URL is available
    if POSTGRES_URL:
        print("Using PostgreSQL for persistence and memory...")
        with PostgresSaver.from_conn_string(POSTGRES_URL) as checkpointer, \
             PostgresStore.from_conn_string(POSTGRES_URL) as store:
            
            # Ensure database tables exist
            checkpointer.setup()
            store.setup()
            
            # Create the Deep Agent with Postgres memory
            agent = create_deep_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                checkpointer=checkpointer,
                store=store
            )
            
            run_agent_demo(agent)
    else:
        print("Warning: POSTGRES_URL not set. Running without persistent memory.")
        # Create the Deep Agent without external persistence (uses default in-memory)
        agent = create_deep_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt
        )
        
        run_agent_demo(agent)

def run_agent_demo(agent):
    """ Helper to run a demo conversation with the agent. """
    # Configuration for persistence (thread-based context)
    config = {"configurable": {"thread_id": "demo-session-1"}}
    
    print("Agent is ready. Thinking...")
    
    # Invoke the agent
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Hello! Do you remember my name? What's the time?"}]
    }, config=config)
    
    print("\n--- Agent Response ---")
    print(result["messages"][-1].content)
    
    # Second turn to verify persistence
    print("\n--- Testing Persistence (Second Turn) ---")
    result = agent.invoke({
        "messages": [{"role": "user", "content": "What was my name again?"}]
    }, config=config)
    print(result["messages"][-1].content)

if __name__ == "__main__":
    main()
