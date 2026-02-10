from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from vaultdantic.cli import END_MARKER, START_MARKER, sync_vault_to_env


def test_sync_vault_to_env_writes_values_from_discovered_settings(tmp_path: Path) -> None:
    package_name = "sample_app"
    _write_sample_project(
        root=tmp_path,
        package_name=package_name,
        vault_values={"EXAMPLE_API_TOKEN": "abc123", "EXAMPLE_WORKSPACE_ID": "workspace-1"},
    )

    result = sync_vault_to_env(project_root=tmp_path)

    env_contents = (tmp_path / ".env").read_text(encoding="utf-8")
    assert START_MARKER in env_contents
    assert "EXAMPLE_API_TOKEN=abc123" in env_contents
    assert "EXAMPLE_WORKSPACE_ID=workspace-1" in env_contents
    assert env_contents.strip().endswith(END_MARKER)

    assert result.settings_models_found == 1
    assert result.providers_queried == 1
    assert result.variables_written == 2


def test_sync_vault_to_env_replaces_existing_managed_block(tmp_path: Path) -> None:
    package_name = "sample_app"
    _write_sample_project(
        root=tmp_path,
        package_name=package_name,
        vault_values={"EXAMPLE_API_TOKEN": "new-token"},
    )

    env_file = tmp_path / ".env"
    env_file.write_text(
        dedent(
            f"""
            KEEP_THIS=1

            {START_MARKER}
            EXAMPLE_API_TOKEN=old-token
            {END_MARKER}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    sync_vault_to_env(project_root=tmp_path, env_file=env_file)

    env_contents = env_file.read_text(encoding="utf-8")
    assert "KEEP_THIS=1" in env_contents
    assert env_contents.count(START_MARKER) == 1
    assert env_contents.count(END_MARKER) == 1
    assert "EXAMPLE_API_TOKEN=old-token" not in env_contents
    assert "EXAMPLE_API_TOKEN=new-token" in env_contents
    assert env_contents.strip().endswith(END_MARKER)


def _write_sample_project(root: Path, package_name: str, vault_values: dict[str, str]) -> None:
    package_dir = root / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "settings.py").write_text(
        dedent(
            f"""
            from pydantic_settings import BaseSettings, SettingsConfigDict

            from vaultdantic import VaultMixin
            from vaultdantic.vaults.base import VaultConfigDict


            class StaticVaultConfig(VaultConfigDict):
                def get_vars(self) -> dict[str, str]:
                    return {vault_values!r}


            class ExampleSettings(BaseSettings, VaultMixin):
                model_config = SettingsConfigDict(env_prefix="EXAMPLE_", extra="ignore")
                model_vault_config = StaticVaultConfig()

                api_token: str
                workspace_id: str
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
