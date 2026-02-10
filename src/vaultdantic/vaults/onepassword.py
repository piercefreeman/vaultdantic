from __future__ import annotations

import json
import subprocess
from typing import Any, Literal

from vaultdantic.vaults.base import VaultConfigDict


class OnePasswordConfigDict(VaultConfigDict):
    provider: Literal["1password"] = "1password"
    vault: str
    entry: str
    executable: str = "op"

    def get_vars(self) -> dict[str, Any]:
        command = [
            self.executable,
            "item",
            "get",
            self.entry,
            "--vault",
            self.vault,
            "--format",
            "json",
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "1Password CLI executable was not found. Install `op` or set executable."
            ) from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() if exc.stderr else "unknown error"
            raise RuntimeError(f"Failed to read item from 1Password: {message}") from exc

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse 1Password CLI JSON response.") from exc

        return _extract_field_values(payload)


def _extract_field_values(payload: dict[str, Any]) -> dict[str, Any]:
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return {}

    values: dict[str, Any] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue

        label = field.get("label")
        value = field.get("value")
        if isinstance(label, str) and label and value is not None:
            values[label] = value

    return values
