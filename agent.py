import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from langchain_core.tools import tool

# Load environment variables from .env file
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
SA_KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH")

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
    
    # Create the Deep Agent
    agent = create_deep_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt="You are a simple and helpful assistant using Gemini on Vertex AI. You can use tools if needed."
    )
    
    # Configuration for persistence (memory)
    config = {"configurable": {"thread_id": "demo-session-1"}}
    
    print("Agent is ready. Thinking...")
    
    # Invoke the agent
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Hello! Can you tell me what your name is?"}]
    }, config=config)
    
    print("\n--- Agent Response ---")
    # In deepagents, the response is usually the last message in the list
    print(result["messages"][-1].content)

if __name__ == "__main__":
    main()
