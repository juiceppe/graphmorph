from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from pydantic import SecretStr

from graphmorph.state import AgentState
from graphmorph.tools import ALL_TOOLS
from graphmorph.config import get_config

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SCHEMA_EXPORT_PROMPT = """You are a Schema Export Agent. Your job is to extract API schemas from any endpoint."""

# ---------------------------------------------------------------------------
# Agent Node Function
# ---------------------------------------------------------------------------

def create_schema_export_agent():
    config = get_config()

    llm = ChatAnthropic(
        model_name= config.model_name,
        temperature=config.temperature,
        api_key=SecretStr(config.anthropic_api_key),
        timeout=config.request_timeout,
        #stop=["\n"]
    )

    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState) -> dict:
        system = SystemMessage(content=SCHEMA_EXPORT_PROMPT)
        messages = [system] + list(state.get("messages", []))

        response = llm_with_tools.invoke(messages)

        return {"messages": [response]}

    return agent_node

schema_export_agent = create_schema_export_agent()
