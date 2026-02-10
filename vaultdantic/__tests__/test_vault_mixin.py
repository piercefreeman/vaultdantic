from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from vaultdantic import VaultMixin
from vaultdantic.vaults.base import VaultConfigDict


class CountingVaultConfig(VaultConfigDict):
    values: dict[str, Any]
    calls: int = 0

    def get_vars(self) -> dict[str, Any]:
        self.calls += 1
        return self.values


def test_env_values_override_vault(monkeypatch: Any) -> None:
    provider = CountingVaultConfig(
        values={"FRAMEIO_TOKEN": "vault-token", "FRAMEIO_DESTINATION_ID": "vault-destination"}
    )

    class FrameioSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="FRAMEIO_", extra="ignore")
        model_vault_config = provider

        token: SecretStr
        destination_id: str

    monkeypatch.setenv("FRAMEIO_TOKEN", "env-token")

    settings = cast(Any, FrameioSettings)()

    assert settings.token.get_secret_value() == "env-token"
    assert settings.destination_id == "vault-destination"
    assert provider.calls == 1


def test_complete_env_values_skip_vault(monkeypatch: Any) -> None:
    provider = CountingVaultConfig(
        values={"FRAMEIO_TOKEN": "vault-token", "FRAMEIO_DESTINATION_ID": "vault-destination"}
    )

    class FrameioSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="FRAMEIO_", extra="ignore")
        model_vault_config = provider

        token: SecretStr
        destination_id: str

    monkeypatch.setenv("FRAMEIO_TOKEN", "env-token")
    monkeypatch.setenv("FRAMEIO_DESTINATION_ID", "env-destination")

    settings = cast(Any, FrameioSettings)()

    assert settings.token.get_secret_value() == "env-token"
    assert settings.destination_id == "env-destination"
    assert provider.calls == 0


def test_dotenv_values_skip_vault(tmp_path: Any) -> None:
    provider = CountingVaultConfig(
        values={"FRAMEIO_TOKEN": "vault-token", "FRAMEIO_DESTINATION_ID": "vault-destination"}
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FRAMEIO_TOKEN=file-token\nFRAMEIO_DESTINATION_ID=file-destination\n", encoding="utf-8"
    )

    class FrameioSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(
            env_file=env_file,
            env_file_encoding="utf-8",
            env_prefix="FRAMEIO_",
            extra="ignore",
        )
        model_vault_config = provider

        token: SecretStr
        destination_id: str

    settings = cast(Any, FrameioSettings)()

    assert settings.token.get_secret_value() == "file-token"
    assert settings.destination_id == "file-destination"
    assert provider.calls == 0


def test_env_style_vault_keys_map_to_field_names() -> None:
    provider = CountingVaultConfig(
        values={"FRAMEIO_TOKEN": "vault-token", "FRAMEIO_DESTINATION_ID": "vault-destination"}
    )

    class FrameioSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="FRAMEIO_", extra="ignore")
        model_vault_config = provider

        token: SecretStr
        destination_id: str

    settings = cast(Any, FrameioSettings)()

    assert settings.token.get_secret_value() == "vault-token"
    assert settings.destination_id == "vault-destination"
    assert provider.calls == 1


def test_nested_settings_with_different_prefixes(monkeypatch: Any) -> None:
    parent_provider = CountingVaultConfig(values={"PARENT_NAME": "parent-vault"})
    child_provider = CountingVaultConfig(values={"CHILD_TOKEN": "child-vault"})

    class ChildSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="CHILD_", extra="ignore")
        model_vault_config = child_provider

        token: SecretStr

    class ParentSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="PARENT_", extra="ignore")
        model_vault_config = parent_provider

        name: str
        child: ChildSettings = Field(default_factory=cast(Any, ChildSettings))

    monkeypatch.setenv("CHILD_TOKEN", "child-env")

    settings = cast(Any, ParentSettings)()

    assert settings.name == "parent-vault"
    assert settings.child.token.get_secret_value() == "child-env"
    assert parent_provider.calls == 1
    assert child_provider.calls == 0


def test_nested_parent_prefix_with_nested_delimiter_uses_parent_env_key() -> None:
    provider = CountingVaultConfig(
        values={
            "PARENT_NAME": "parent-vault",
            "PARENT_CHILD__TOKEN": "child-vault",
        }
    )

    class ChildModel(BaseModel):
        token: str

    class ParentSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(
            env_prefix="PARENT_",
            env_nested_delimiter="__",
            extra="ignore",
        )
        model_vault_config = provider

        name: str
        child: ChildModel

    settings = cast(Any, ParentSettings)()

    assert settings.name == "parent-vault"
    assert settings.child.token == "child-vault"
    assert provider.calls == 1


def test_nested_parent_prefix_without_nested_delimiter_does_not_expand_nested_keys() -> None:
    provider = CountingVaultConfig(
        values={
            "PARENT_NAME": "parent-vault",
            "PARENT_CHILD_TOKEN": "child-vault",
        }
    )

    class ChildModel(BaseModel):
        token: str

    class ParentSettings(BaseSettings, VaultMixin):
        model_config = SettingsConfigDict(env_prefix="PARENT_", extra="ignore")
        model_vault_config = provider

        name: str
        child: ChildModel

    with pytest.raises(ValidationError, match="child"):
        cast(Any, ParentSettings)()
    assert provider.calls == 1
