"""Print the service's OpenAPI contract (committed as contracts/analyzer-api.openapi.json).

Usage:  uv run python -m apisentinel.api.contract > ../contracts/analyzer-api.openapi.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import SecretStr

from apisentinel.api.app import create_app
from apisentinel.api.settings import Settings


def build_contract() -> dict[str, Any]:
    # A throwaway token: the contract does not depend on configuration values.
    settings = Settings(internal_token=SecretStr("contract-export-" + "x" * 32))
    schema: dict[str, Any] = create_app(settings).openapi()
    return schema


def main() -> None:
    sys.stdout.write(json.dumps(build_contract(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
