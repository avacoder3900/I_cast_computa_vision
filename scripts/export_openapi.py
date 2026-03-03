"""Export the OpenAPI spec to generated/openapi.json."""

import json
from pathlib import Path

from icast_cv.main import app


def main() -> None:
    spec = app.openapi()
    out = Path("generated/openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
