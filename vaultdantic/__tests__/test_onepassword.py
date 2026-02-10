from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vaultdantic.vaults.onepassword import OnePasswordConfigDict


def test_get_vars_reads_cli_json_and_maps_labels() -> None:
    config = OnePasswordConfigDict(vault="Engineering", entry="frameio-service")
    mock_result = MagicMock()
    mock_result.stdout = """
    {
      "id": "abcd1234",
      "title": "frameio-service",
      "fields": [
        {"label": "token", "type": "CONCEALED", "value": "abc123"},
        {"label": "destination_id", "type": "CONCEALED", "value": "dest-123"},
        {"label": "ignored", "type": "CONCEALED", "value": null},
        {"label": "", "type": "CONCEALED", "value": "skip"}
      ]
    }
    """

    with patch(
        "vaultdantic.vaults.onepassword.subprocess.run", return_value=mock_result
    ) as run_mock:
        values = config.get_vars()

    assert values == {
        "token": "abc123",
        "destination_id": "dest-123",
    }
    run_mock.assert_called_once_with(
        [
            "op",
            "item",
            "get",
            "frameio-service",
            "--vault",
            "Engineering",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_get_vars_raises_when_cli_missing() -> None:
    config = OnePasswordConfigDict(vault="Engineering", entry="frameio-service")

    with patch(
        "vaultdantic.vaults.onepassword.subprocess.run",
        side_effect=FileNotFoundError("op not found"),
    ):
        with pytest.raises(RuntimeError, match="1Password CLI executable was not found"):
            config.get_vars()


def test_get_vars_raises_when_cli_fails() -> None:
    config = OnePasswordConfigDict(vault="Engineering", entry="frameio-service")
    process_error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["op"],
        stderr="unauthorized",
    )

    with patch("vaultdantic.vaults.onepassword.subprocess.run", side_effect=process_error):
        with pytest.raises(RuntimeError, match="Failed to read item from 1Password: unauthorized"):
            config.get_vars()


def test_get_vars_raises_for_invalid_json() -> None:
    config = OnePasswordConfigDict(vault="Engineering", entry="frameio-service")
    mock_result = MagicMock()
    mock_result.stdout = "{not-json"

    with patch("vaultdantic.vaults.onepassword.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to parse 1Password CLI JSON response"):
            config.get_vars()


def test_get_vars_raises_for_schema_mismatch() -> None:
    config = OnePasswordConfigDict(vault="Engineering", entry="frameio-service")
    mock_result = MagicMock()
    mock_result.stdout = """
    {
      "id": "abcd1234",
      "title": "frameio-service",
      "fields": [
        {"label": "token", "value": "abc123"}
      ]
    }
    """

    with patch("vaultdantic.vaults.onepassword.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="did not match expected schema"):
            config.get_vars()
