
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from graphmorph.state import AgentState
from graphmorph.workflows.export import build_export_subgraph
from graphmorph.workflows.parser import build_parser_subgraph


def build_conditional_pipeline(checkpointer=None):
    """Export → (validate) → Parse or Skip"""

    pipeline = StateGraph(AgentState)

    pipeline.add_node("export", build_export_subgraph())
    pipeline.add_node("parse", build_parser_subgraph())

    # Custom validation node (not a subgraph, just a function)
    def check_export_success(state: AgentState) -> dict:
        # Check if export worked
        messages = state.get("messages", [])
        for msg in messages:
            if "ERROR" in str(getattr(msg, "content", "")):
                return {"status": "failed"}
        return {"status": "success"}

    pipeline.add_node("validate", check_export_success)

    # Prepare state for parser by adding a clear instruction
    def prepare_for_parsing(state: AgentState) -> dict:
        raw_schema = state.get("raw_schema")
        if raw_schema:
            # Add explicit instruction for the parser agent
            parsing_instruction = HumanMessage(
                content=f"Now parse this schema into structured entities:\n\n{raw_schema}"
            )
            return {"messages": [parsing_instruction]}
        return {}

    pipeline.add_node("prepare_parse", prepare_for_parsing)

    # Routing function
    def route_after_validation(state: AgentState) -> str:
        if state.get("status") == "failed":
            return "end"
        return "prepare_parse"

    # Wire it up
    pipeline.add_edge(START, "export")
    pipeline.add_edge("export", "validate")
    pipeline.add_conditional_edges(
        "validate",
        route_after_validation,
        {"prepare_parse": "prepare_parse", "end": END}
    )
    pipeline.add_edge("prepare_parse", "parse")
    pipeline.add_edge("parse", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return pipeline.compile(checkpointer=checkpointer)