import json
from langchain_core.tools import tool
from typing_inspection.typing_objects import is_required

from graphmorph.state import SchemaEntity, SchemaField

# --------------------
# GraphQL Parsing
# --------------------

def _unwrap_graphql_type(type_info: dict) -> tuple[str, bool]:

    is_required= False
    current = type_info
    type_parts =[]

    while current:
        kind = current.get("kind")
        name = current.get("name")

        if kind == "NON_NULL":
            is_required = True
            current = current.get("ofType", {})
        elif kind == "LIST":
            type_parts.append("[")
            current = current.get("ofType", {})
        elif name:
            type_parts.append(name)
            break
        else:
            current = current.get("ofType", {})
            if not current:
                type_parts.append("Unknown")
                break

    type_name = "".join(type_parts)
    type_name += "]" * type_name.count("[")

    return type_name, is_required

def _parse_graphql_type(type_def: dict, source_api: str) -> SchemaEntity | None:

    name = type_def.get("name", "")
    kind = type_def.get("kind", "UNKNOWN")

    if name.startswith("__"):
        return None

    if kind == "SCALAR":
        return None

    fields: list[SchemaField] = []

    raw_fields = type_def.get("fields") or []

    if not raw_fields:
        raw_fields = type_def.get("inputFields") or []

    for field in raw_fields:
        field_type_info = field.get("type", {})
        type_name, is_required = _unwrap_graphql_type(field_type_info)

        fields.append(SchemaField(
            name=field.get("name", "unknown"),
            field_type=type_name,
            is_required=is_required,
            description=field.get("description")
        ))

    enum_values = type_def.get("enumValues") or []
    for ev in enum_values:
        fields.append(SchemaField(
            name=ev.get("name", "unknown"),
            field_type="ENUM_VALUE",
            is_required=True,
            description=ev.get("description")
        ))

    return SchemaEntity(
        name=name,
        kind=kind,
        description=type_def.get("description"),
        fields=fields,
        source_api=source_api
    )


@tool
def parse_graphql_schema(raw_schema_json: str, source_api: str) -> str:
    """
      Parse a raw GraphQL introspection result into normalized entities.

      Use this after fetching a GraphQL schema to extract structured entity data.

      Args:
          raw_schema_json: The JSON string of the GraphQL introspection result
          source_api: Name to identify the source API

      Returns:
          A summary of parsed entities, or error message if parsing fails.
      """

    try:

        data = json.loads(raw_schema_json)

        if "data" in data:
            schema = data["data"].get("__schema", {})
        elif "__schema" in data:
            schema = data["__schema"]
        else:
            schema = data

        types = schema.get("types", [])

        if not types:
            return f"ERROR - No types found in GraphQL schema. Is this a valid GraphQL instrospection result?"

        entities: list[SchemaEntity] = []
        for type_def in types:
            entity = _parse_graphql_type(type_def, source_api)
            if entity:
                entities.append(entity)

        summary_lines = [
            f"SUCCESS - Parsed {len(entities)} entities from GraphQL schema for '{source_api}'.",
        ]

        by_kind = dict[str, list[SchemaEntity]] = {}
        for e in entities:
            if e["kind"] not in by_kind:
                by_kind[e["kind"]] = []
            by_kind[e["kind"]].append(e)
        for kind, kind_entities in sorted(by_kind.items()):
            summary_lines.append(f"\n{kind} ({len(kind_entities)}):")
            for e in kind_entities[:5]:
                field_count = len(e["fields"])
                summary_lines.append(f"  • {e['name']} - {field_count} fields")
            if len(kind_entities) > 5:
                summary_lines.append(f"  ... and {len(kind_entities) - 5} more")
            summary_lines.append("")

            summary_lines.append("---ENTITIES_JSON---")
            summary_lines.append(json.dumps([dict(e) for e in entities], indent=2))

            return "/n".join(summary_lines)

    except json.JSONDecodeError as e:
        return f"ERROR - Invalid JSON: {str(e)}"
    except Exception as e:
        return f"ERROR - Failed to parse GraphQL schema: {str(e)}"


# ---------------------------------------------------------------------------
# OpenAPI Parsing
# ---------------------------------------------------------------------------

def _resolve_openapi_ref(ref: str) -> str:
    """Extract the type name from an OpenAPI $ref."""
    # $ref looks like: "#/components/schemas/Pet" or "#/definitions/Pet"
    return ref.split("/")[-1]


def _parse_openapi_type(prop_def: dict) -> str:
    """
    Convert an OpenAPI property definition to a type string.

    Handles:
    - Basic types: string, integer, boolean, etc.
    - References: $ref to other schemas
    - Arrays: type: array with items
    - Objects: nested objects
    """
    # Handle references
    if "$ref" in prop_def:
        return _resolve_openapi_ref(prop_def["$ref"])

    prop_type = prop_def.get("type", "object")

    # Handle arrays
    if prop_type == "array":
        items = prop_def.get("items", {})
        if "$ref" in items:
            item_type = _resolve_openapi_ref(items["$ref"])
        else:
            item_type = items.get("type", "object")
        return f"[{item_type}]"

    # Map OpenAPI types to more generic names
    type_mapping = {
        "string": "String",
        "integer": "Int",
        "number": "Float",
        "boolean": "Boolean",
        "object": "Object",
    }

    return type_mapping.get(prop_type, prop_type)


def _parse_openapi_schema(name: str, schema_def: dict, source_api: str) -> SchemaEntity:
    """
    Parse a single OpenAPI schema definition into a SchemaEntity.
    """
    # Determine the kind
    schema_type = schema_def.get("type", "object")
    if "enum" in schema_def:
        kind = "ENUM"
    elif schema_type == "object" or "properties" in schema_def:
        kind = "OBJECT"
    elif "allOf" in schema_def:
        kind = "COMPOSITE"
    else:
        kind = "OBJECT"

    fields: list[SchemaField] = []

    # Get required fields
    required_fields = set(schema_def.get("required", []))

    # Parse properties
    properties = schema_def.get("properties", {})
    for prop_name, prop_def in properties.items():
        field_type = _parse_openapi_type(prop_def)

        fields.append(SchemaField(
            name=prop_name,
            field_type=field_type,
            is_required=prop_name in required_fields,
            description=prop_def.get("description"),
        ))

    # Handle enums
    if "enum" in schema_def:
        for value in schema_def["enum"]:
            fields.append(SchemaField(
                name=str(value),
                field_type="ENUM_VALUE",
                is_required=True,
                description=None,
            ))

    return SchemaEntity(
        name=name,
        kind=kind,
        description=schema_def.get("description"),
        fields=fields,
        source_api=source_api,
    )


@tool
def parse_openapi_spec(raw_spec_json: str, source_api: str) -> str:
    """
    Parse a raw OpenAPI specification into normalized entities.

    Use this after fetching an OpenAPI spec to extract structured entity data.

    Args:
        raw_spec_json: The JSON string of the OpenAPI specification
        source_api: Name to identify the source API

    Returns:
        A summary of parsed entities, or error message if parsing fails.
    """
    try:
        # Parse the JSON
        spec = json.loads(raw_spec_json)

        # Find schemas - different locations for OpenAPI 3.x vs Swagger 2.x
        schemas = spec.get("components", {}).get("schemas", {})
        if not schemas:
            schemas = spec.get("definitions", {})

        if not schemas:
            return "ERROR - No schemas found. Is this a valid OpenAPI/Swagger spec?"

        # Parse each schema
        entities: list[SchemaEntity] = []
        for name, schema_def in schemas.items():
            entity = _parse_openapi_schema(name, schema_def, source_api)
            entities.append(entity)

        # Build summary
        summary_lines = [
            f"SUCCESS - Parsed {len(entities)} entities from OpenAPI spec '{source_api}'",
            "",
        ]

        # Group by kind
        by_kind: dict[str, list[SchemaEntity]] = {}
        for e in entities:
            if e["kind"] not in by_kind:
                by_kind[e["kind"]] = []
            by_kind[e["kind"]].append(e)

        for kind, kind_entities in sorted(by_kind.items()):
            summary_lines.append(f"{kind} ({len(kind_entities)}):")
            for e in kind_entities[:5]:
                field_count = len(e["fields"])
                summary_lines.append(f"  • {e['name']} - {field_count} fields")
            if len(kind_entities) > 5:
                summary_lines.append(f"  ... and {len(kind_entities) - 5} more")
            summary_lines.append("")

        # Add the actual entities as JSON
        summary_lines.append("---ENTITIES_JSON---")
        summary_lines.append(json.dumps([dict(e) for e in entities], indent=2))

        return "\n".join(summary_lines)

    except json.JSONDecodeError as e:
        return f"ERROR - Invalid JSON: {str(e)}"
    except Exception as e:
        return f"ERROR - Failed to parse spec: {str(e)}"


# ---------------------------------------------------------------------------
# Tool Collections
# ---------------------------------------------------------------------------

PARSER_TOOLS = [parse_graphql_schema, parse_openapi_spec]
