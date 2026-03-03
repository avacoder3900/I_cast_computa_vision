"""Generate TypeScript types from the OpenAPI spec."""

import json
from pathlib import Path
from typing import Any


def _ts_type(schema: dict[str, Any], schemas: dict[str, Any]) -> str:
    """Convert a JSON Schema type to TypeScript."""
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return ref_name
    if "anyOf" in schema:
        parts = [_ts_type(s, schemas) for s in schema["anyOf"] if s.get("type") != "null"]
        nullable = any(s.get("type") == "null" for s in schema["anyOf"])
        base = " | ".join(parts) if len(parts) > 1 else parts[0] if parts else "unknown"
        return f"{base} | null" if nullable else base
    schema_type = schema.get("type", "any")
    if schema_type == "string":
        if schema.get("format") == "date-time":
            return "string"  # ISO 8601 string in JSON
        return "string"
    if schema_type == "integer" or schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        items = schema.get("items", {})
        return f"Array<{_ts_type(items, schemas)}>"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if additional and isinstance(additional, dict):
            return f"Record<string, {_ts_type(additional, schemas)}>"
        return "Record<string, unknown>"
    return "unknown"


def generate(spec_path: str, out_path: str) -> None:
    spec = json.loads(Path(spec_path).read_text())
    schemas: dict[str, Any] = spec.get("components", {}).get("schemas", {})

    lines: list[str] = [
        "// Auto-generated from OpenAPI spec -- do not edit manually",
        f"// Generated from: {spec.get('info', {}).get('title', '')} v{spec.get('info', {}).get('version', '')}",
        "",
    ]

    for name, schema in schemas.items():
        props: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])

        if not props:
            continue

        lines.append(f"export interface {name} {{")
        for prop_name, prop_schema in props.items():
            optional = "" if prop_name in required else "?"
            ts_type = _ts_type(prop_schema, schemas)
            lines.append(f"  {prop_name}{optional}: {ts_type};")
        lines.append("}")
        lines.append("")

    # API client helper type
    lines.extend([
        "// API endpoint paths",
        "export const API_PATHS = {",
        "  health: '/health',",
        "  samples: '/api/v1/samples',",
        "  sample: (id: string) => `/api/v1/samples/${id}`,",
        "  sampleImages: (id: string) => `/api/v1/samples/${id}/images`,",
        "  images: '/api/v1/images',",
        "  imageFile: (id: string) => `/api/v1/images/${id}/file`,",
        "  imageThumbnail: (id: string) => `/api/v1/images/${id}/thumbnail`,",
        "  capture: '/api/v1/capture',",
        "  cameras: '/api/v1/cameras',",
        "  cameraStatus: (index: number) => `/api/v1/cameras/${index}/status`,",
        "} as const;",
        "",
    ])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    generate("generated/openapi.json", "generated/icast-cv-api.ts")
