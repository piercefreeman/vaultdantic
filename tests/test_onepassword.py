from vaultdantic.vaults.onepassword import _extract_field_values


def test_extract_field_values() -> None:
    payload = {
        "fields": [
            {"label": "token", "value": "abc123"},
            {"label": "destination_id", "value": "dest-123"},
            {"label": "empty", "value": None},
            {"label": "", "value": "ignored"},
            "invalid",
        ]
    }

    values = _extract_field_values(payload)

    assert values == {
        "token": "abc123",
        "destination_id": "dest-123",
    }
