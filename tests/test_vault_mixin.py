from __future__ import annotations

from typing import Any, cast

from pydantic import SecretStr
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
        values={"token": "vault-token", "destination_id": "vault-destination"}
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
        values={"token": "vault-token", "destination_id": "vault-destination"}
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
        values={"token": "vault-token", "destination_id": "vault-destination"}
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
