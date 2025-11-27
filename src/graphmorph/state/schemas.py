from typing import TypedDict, Annotated, Optional, Literal
from operator import add
from langchain_core.messages import BaseMessage

class APIInfo(TypedDict, total=False):
    endpoint: str
    name: str
    api_type: Literal["graphql", "rest"] | None
    spec_url: str | None

class SchemaField(TypedDict):
    name: str
    field_type: str
    is_required: bool
    description: str | None

class SchemaEntity(TypedDict):
    name: str
    kind: str
    description: str | None
    fields: list[SchemaField]
    source_api: str

class AgentState(TypedDict, total=False):

    messages: Annotated[list[BaseMessage], add]

    current_api: APIInfo | None

    raw_schema: dict | None

    entities: Annotated[list[SchemaEntity], add]

    errors: Annotated[list[str], add]

    status: str

def create_initial_state(endpoint: str, name: str | None = None) -> AgentState:
    if name is None:
        name = endpoint.split("/")[-1]
    return AgentState(
        messages=[],
        current_api=APIInfo(
            endpoint=endpoint,
            name=name,
            api_type=None,
            spec_url=None
        ),
        raw_schema=None,
        entities=[],
        errors=[],
        status="initialized"
    )