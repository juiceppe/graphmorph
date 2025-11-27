from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from graphmorph.state import AgentState
from graphmorph.tools.parser_tools import PARSER_TOOLS
from graphmorph.agents import create_parser_agent

def build_parser_workflow(checkpointer=None):
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", create_parser_agent())

    workflow.add_node("tools", ToolNode(PARSER_TOOLS))

    workflow.add_edge(START, "agent")

    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: END
        }
    )

    workflow.add_edge("tools", "agent")

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)

def build_parser_subgraph():

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", create_parser_agent())
    workflow.add_node("tools", ToolNode(PARSER_TOOLS))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: END
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()

def parse_schema(raw_schema_json: str, source_api: str = "UnknownAPI") -> dict:

    from langchain_core.messages import HumanMessage

    state: AgentState = {
        "messages": [
            HumanMessage(content=f"Parse this schema from '{source_api}':\n\n{raw_schema_json}")
        ],
        "current_api": {"name": source_api, "endpoint": "", "api_type": None, "spec_url": None},
        "raw_schema": None,
        "entities": [],
        "errors": [],
        "status": "parsing",
    }

    workflow = build_parser_workflow()
    config = {"configurable": {"thread_id": f"parse-{source_api}"}}

    return workflow.invoke(state, config)

# Standalone workflow
parser_workflow = build_parser_workflow()

# Subgraph for composition
parser_subgraph = build_parser_subgraph()