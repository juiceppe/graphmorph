import httpx
from langchain_core.tools import tool

from graphmorph.config import get_config


# ---------------------------------------------------------------------------
# GraphQL Tools
# ---------------------------------------------------------------------------

@tool
def check_graphql_endpoint(endpoint: str) -> str:
    """
    Check if an endpoint supports GraphQL by attempting introspection.

    Use this FIRST when analyzing an unknown API to determine if it's GraphQL.

    Args:
        endpoint: The URL to check (e.g., https://api.example.com/graphql)

    Returns:
        A message indicating whether GraphQL is supported, with details.
    """
    # Simple introspection query - just asks for type names
    # If this works, it's definitely GraphQL
    test_query = {"query": "{ __schema { types { name } } }"}

    config = get_config()

    try:
        with httpx.Client(timeout=config.request_timeout) as client:
            response = client.post(
                endpoint,
                json=test_query,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data and "__schema" in data["data"]:
                    type_count = len(data["data"]["__schema"]["types"])
                    return f"YES - This is a GraphQL endpoint. Found {type_count} types via introspection."
                elif "errors" in data:
                    return f"MAYBE - Endpoint responded but with errors: {data['errors'][0].get('message', 'Unknown error')}"

            return f"NO - Endpoint returned status {response.status_code}. Not a GraphQL endpoint."

    except httpx.TimeoutException:
        return f"ERROR - Request timed out after {config.request_timeout} seconds."
    except httpx.RequestError as e:
        return f"ERROR - Could not connect to endpoint: {str(e)}"
    except Exception as e:
        return f"ERROR - Unexpected error: {str(e)}"


@tool
def fetch_graphql_schema(endpoint: str) -> str:
    """
    Fetch the complete GraphQL schema via introspection.

    IMPORTANT: Only call this AFTER confirming the endpoint is GraphQL
    using check_graphql_endpoint.

    Args:
        endpoint: The GraphQL endpoint URL

    Returns:
        A summary of the schema including all types, their kinds, and field counts.
    """
    # Full introspection query - gets everything we need
    introspection_query = """
    query IntrospectionQuery {
        __schema {
            queryType { name }
            mutationType { name }
            types {
                name
                kind
                description
                fields {
                    name
                    description
                    type {
                        name
                        kind
                        ofType {
                            name
                            kind
                            ofType {
                                name
                                kind
                            }
                        }
                    }
                }
                inputFields {
                    name
                    type {
                        name
                        kind
                    }
                }
                enumValues {
                    name
                    description
                }
            }
        }
    }
    """

    config = get_config()

    try:
        with httpx.Client(timeout=config.request_timeout) as client:
            response = client.post(
                endpoint,
                json={"query": introspection_query},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                return f"ERROR - Server returned status {response.status_code}"

            data = response.json()

            if "errors" in data:
                return f"ERROR - GraphQL errors: {data['errors']}"

            schema = data.get("data", {}).get("__schema", {})
            types = schema.get("types", [])

            # Filter out internal types (those starting with __)
            user_types = [t for t in types if not t["name"].startswith("__")]

            # Build a summary
            summary_lines = [
                f"SUCCESS - Fetched GraphQL schema with {len(user_types)} types.",
                "",
                "Schema summary:",
            ]

            # Group types by kind
            by_kind: dict[str, list] = {}
            for t in user_types:
                kind = t["kind"]
                if kind not in by_kind:
                    by_kind[kind] = []
                by_kind[kind].append(t)

            for kind, kind_types in sorted(by_kind.items()):
                summary_lines.append(f"\n{kind} ({len(kind_types)}):")
                for t in kind_types[:10]:  # Limit to first 10 per kind
                    field_count = len(t.get("fields") or t.get("inputFields") or t.get("enumValues") or [])
                    desc = f" - {t['description'][:50]}..." if t.get("description") else ""
                    summary_lines.append(f"  • {t['name']} ({field_count} fields){desc}")
                if len(kind_types) > 10:
                    summary_lines.append(f"  ... and {len(kind_types) - 10} more")

            return "\n".join(summary_lines)

    except httpx.TimeoutException:
        return f"ERROR - Request timed out after {config.request_timeout} seconds."
    except Exception as e:
        return f"ERROR - Failed to fetch schema: {str(e)}"


# ---------------------------------------------------------------------------
# REST/OpenAPI Tools
# ---------------------------------------------------------------------------

@tool
def check_openapi_endpoint(base_url: str) -> str:
    """
    Check if a REST API has an OpenAPI/Swagger specification available.

    This searches common locations where OpenAPI specs are typically hosted.
    Use this when check_graphql_endpoint returns NO.

    Args:
        base_url: The base URL of the API (e.g., https://api.example.com)

    Returns:
        The URL where the OpenAPI spec was found, or a message if not found.
    """
    # Common paths where OpenAPI specs live
    common_paths = [
        "/openapi.json",
        "/openapi.yaml",
        "/swagger.json",
        "/swagger.yaml",
        "/api-docs",
        "/v3/api-docs",
        "/v2/api-docs",
        "/docs/openapi.json",
        "/.well-known/openapi.json",
        "/api/openapi.json",
    ]

    base_url = base_url.rstrip("/")
    config = get_config()

    found_specs = []

    try:
        with httpx.Client(timeout=config.request_timeout, follow_redirects=True) as client:
            for path in common_paths:
                try:
                    url = f"{base_url}{path}"
                    response = client.get(url)

                    if response.status_code == 200:
                        # Try to verify it's actually an OpenAPI spec
                        try:
                            data = response.json()
                            # Check for OpenAPI markers
                            if "openapi" in data or "swagger" in data or "paths" in data:
                                version = data.get("openapi") or data.get("swagger") or "unknown"
                                found_specs.append(f"{url} (version: {version})")
                        except:
                            # Not JSON, might be YAML - still note it
                            if path.endswith(".yaml"):
                                found_specs.append(f"{url} (YAML format)")
                except:
                    continue

        if found_specs:
            return f"YES - Found OpenAPI spec at:\n" + "\n".join(f"  • {s}" for s in found_specs)

        return "NO - No OpenAPI specification found at standard locations."

    except Exception as e:
        return f"ERROR - Failed to check for OpenAPI: {str(e)}"


@tool
def fetch_openapi_spec(spec_url: str) -> str:
    """
    Fetch and summarize an OpenAPI specification.

    IMPORTANT: Only call this AFTER finding the spec URL using check_openapi_endpoint.

    Args:
        spec_url: The URL of the OpenAPI specification

    Returns:
        A summary of the API including endpoints and schemas.
    """
    config = get_config()

    try:
        with httpx.Client(timeout=config.request_timeout, follow_redirects=True) as client:
            response = client.get(spec_url)

            if response.status_code != 200:
                return f"ERROR - Server returned status {response.status_code}"

            spec = response.json()

            # Extract key information
            title = spec.get("info", {}).get("title", "Unknown API")
            version = spec.get("info", {}).get("version", "unknown")
            openapi_version = spec.get("openapi") or spec.get("swagger") or "unknown"

            # Get paths (endpoints)
            paths = spec.get("paths", {})

            # Get schemas (OpenAPI 3.x in components/schemas, Swagger 2.x in definitions)
            schemas = spec.get("components", {}).get("schemas", {}) or spec.get("definitions", {})

            # Build summary
            summary_lines = [
                f"SUCCESS - Fetched OpenAPI spec for '{title}' (API v{version}, OpenAPI {openapi_version})",
                "",
                f"Endpoints ({len(paths)}):",
            ]

            # List first 10 endpoints
            for i, (path, methods) in enumerate(list(paths.items())[:10]):
                method_list = ", ".join(m.upper() for m in methods.keys() if m != "parameters")
                summary_lines.append(f"  • {method_list} {path}")
            if len(paths) > 10:
                summary_lines.append(f"  ... and {len(paths) - 10} more endpoints")

            summary_lines.append(f"\nSchemas ({len(schemas)}):")

            # List first 15 schemas
            for i, (name, schema_def) in enumerate(list(schemas.items())[:15]):
                prop_count = len(schema_def.get("properties", {}))
                schema_type = schema_def.get("type", "object")
                summary_lines.append(f"  • {name} ({schema_type}, {prop_count} properties)")
            if len(schemas) > 15:
                summary_lines.append(f"  ... and {len(schemas) - 15} more schemas")

            return "\n".join(summary_lines)

    except Exception as e:
        return f"ERROR - Failed to fetch OpenAPI spec: {str(e)}"


# ---------------------------------------------------------------------------
# Tool Collections
# ---------------------------------------------------------------------------

DISCOVERY_TOOLS = [check_graphql_endpoint, check_openapi_endpoint]
SCHEMA_TOOLS = [fetch_graphql_schema, fetch_openapi_spec]
ALL_TOOLS = DISCOVERY_TOOLS + SCHEMA_TOOLS
