"""Tools for GraphMorph agents."""

from .api_tools import (
    check_graphql_endpoint,
    check_openapi_endpoint,
    fetch_graphql_schema,
    fetch_openapi_spec,
    DISCOVERY_TOOLS,
    SCHEMA_TOOLS,
    ALL_TOOLS as API_TOOLS,
)

from .parser_tools import (
    parse_graphql_schema,
    parse_openapi_spec,
    PARSER_TOOLS,
)

# Combined tool sets for different agent types
ALL_TOOLS = API_TOOLS + PARSER_TOOLS

__all__ = [
    # API tools
    "check_graphql_endpoint",
    "check_openapi_endpoint",
    "fetch_graphql_schema",
    "fetch_openapi_spec",
    "DISCOVERY_TOOLS",
    "SCHEMA_TOOLS",
    "API_TOOLS",
    # Parser tools
    "parse_graphql_schema",
    "parse_openapi_spec",
    "PARSER_TOOLS",
    # Combined
    "ALL_TOOLS",
]