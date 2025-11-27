from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from pydantic import SecretStr

from graphmorph.config import get_config
from graphmorph.state import AgentState
from graphmorph.tools.parser_tools import PARSER_TOOLS


PARSER_AGENT_PROMPT = """You are a Schema Parser Agent. Your job is to transform raw API schemas into normalized, structured entities."""

def create_parser_agent():
    config = get_config()


    llm = ChatAnthropic(
        model_name= config.model_name,
        temperature=config.temperature,
        api_key=SecretStr(config.anthropic_api_key),
        timeout=config.request_timeout,
    )

    llm_with_tools = llm.bind_tools(PARSER_TOOLS)

    def agent_node(state: AgentState) -> dict:

        system = SystemMessage(content=PARSER_AGENT_PROMPT)
        messages = [system] + list(state.get("messages", []))

        response = llm_with_tools.invoke(messages)

        return {"messages": [response]}

    return agent_node

parser_agent = create_parser_agent()