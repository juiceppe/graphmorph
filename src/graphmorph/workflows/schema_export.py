from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from graphmorph.state import AgentState
from graphmorph.tools import ALL_TOOLS
from graphmorph.agents import create_schema_export_agent

def build_schema_export_workflow(checkpointer=None):
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", create_schema_export_agent())

    workflow.add_node("tools", ToolNode(ALL_TOOLS))

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

def export_api_schema(endpoint: str, name: str | None = None) -> dict:

    from langchain_core.messages import HumanMessage
    from graphmorph.state import create_initial_state

    state = create_initial_state(endpoint, name)

    state["messages"] = [HumanMessage(content=f"Please analyze this API and export its schema: {endpoint}")]

    workflow = build_schema_export_workflow()

    config = {"configurable": {"thread_id": f"export-{endpoint}"}}

    result = workflow.invoke(state, config)

    return result


schema_export_workflow = build_schema_export_workflow()