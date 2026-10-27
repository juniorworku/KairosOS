"""Export the API contract without connecting to infrastructure.

Run from api/: python -m app.export_openapi
"""

import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    output = Path(__file__).resolve().parent.parent / "openapi.json"
    output.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
