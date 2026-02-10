from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseEnvSettingsSource

from vaultdantic.vaults.base import VaultConfigDict


class VaultSettingsSource(PydanticBaseEnvSettingsSource):
    """Late settings source that maps env-style vault keys to settings fields."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls=settings_cls)
        self._vault_env_vars: dict[str, Any] = {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        for field_key, env_name, value_is_complex in self._extract_field_info(field, field_name):
            if env_name in self._vault_env_vars:
                return self._vault_env_vars[env_name], field_key, value_is_complex
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        vault_config = getattr(self.settings_cls, "model_vault_config", None)
        if vault_config is None:
            return {}
        if not isinstance(vault_config, VaultConfigDict):
            raise TypeError(
                f"{self.settings_cls.__name__}.model_vault_config must be a VaultConfigDict instance."
            )

        if not self._has_missing_required_fields():
            return {}

        vault_values = dict(vault_config.get_vars())
        if not vault_values:
            return {}

        self._vault_env_vars = {
            self._apply_case_sensitive(str(key)): value for key, value in vault_values.items()
        }
        resolved_vault_values = super().__call__()
        current_keys = set(self.current_state.keys())
        return {
            key: value for key, value in resolved_vault_values.items() if key not in current_keys
        }

    def _has_missing_required_fields(self) -> bool:
        current_keys = set(self.current_state.keys())
        for field_name, field in self.settings_cls.model_fields.items():
            if not field.is_required():
                continue

            accepted_keys = {field_name}
            accepted_keys.update(
                field_key for field_key, _, _ in self._extract_field_info(field, field_name)
            )
            if not accepted_keys.intersection(current_keys):
                return True

        return False


class VaultMixin:
    """Mixin that appends a vault source as the lowest-priority settings source."""

    model_config = SettingsConfigDict(ignored_types=(VaultConfigDict,))
    model_vault_config: ClassVar[VaultConfigDict | None] = None
    _vaultdantic_original_settings_customise_sources: ClassVar[
        Callable[..., tuple[PydanticBaseSettingsSource, ...]] | None
    ] = None
    _vaultdantic_wrapped_sources: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if not issubclass(cls, BaseSettings):
            return
        if cls.__dict__.get("_vaultdantic_wrapped_sources", False):
            return

        original = cls.settings_customise_sources

        def _wrapped_settings_customise_sources(
            cls: type[BaseSettings],
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            sources = tuple(
                original(
                    settings_cls,
                    init_settings,
                    env_settings,
                    dotenv_settings,
                    file_secret_settings,
                )
            )
            return (*sources, VaultSettingsSource(settings_cls))

        cls._vaultdantic_original_settings_customise_sources = original
        cls.settings_customise_sources = classmethod(_wrapped_settings_customise_sources)
        cls._vaultdantic_wrapped_sources = True
