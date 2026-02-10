from __future__ import annotations

import subprocess
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from vaultdantic.vaults.base import VaultConfigDict


class OnePasswordItemField(BaseModel):
    """Validated subset of the 1Password item field schema."""

    model_config = ConfigDict(extra="ignore")

    label: str
    type: str
    value: Any | None = None


class OnePasswordItemResponse(BaseModel):
    """Validated subset of the 1Password 'op item get --format json' schema."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    fields: list[OnePasswordItemField]


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

        item = _parse_item_response(result.stdout)

        return _extract_field_values(item)


def _parse_item_response(payload_json: str) -> OnePasswordItemResponse:
    try:
        return OnePasswordItemResponse.model_validate_json(payload_json)
    except ValidationError as exc:
        if any(error.get("type") == "json_invalid" for error in exc.errors()):
            raise RuntimeError("Failed to parse 1Password CLI JSON response.") from exc
        raise RuntimeError("1Password CLI output did not match expected schema.") from exc


def _extract_field_values(item: OnePasswordItemResponse) -> dict[str, Any]:
    fields = item.fields

    values: dict[str, Any] = {}
    for field in fields:
        if field.label and field.value is not None:
            values[field.label] = field.value

    return values
