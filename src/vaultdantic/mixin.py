from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from vaultdantic.vaults.base import VaultConfigDict


class VaultSettingsSource(PydanticBaseSettingsSource):
    """Late settings source that fills missing model fields from a vault provider."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        vault_config = getattr(self.settings_cls, "model_vault_config", None)
        if vault_config is None:
            return {}
        if not isinstance(vault_config, VaultConfigDict):
            raise TypeError(
                f"{self.settings_cls.__name__}.model_vault_config must be a VaultConfigDict instance."
            )

        required_fields = {
            name
            for name, model_field in self.settings_cls.model_fields.items()
            if model_field.is_required()
        }
        if not required_fields:
            return {}

        current_keys = set(self.current_state.keys())
        if required_fields.issubset(current_keys):
            return {}

        vault_values = dict(vault_config.get_vars())
        if not vault_values:
            return {}

        model_fields = set(self.settings_cls.model_fields.keys())
        return {
            key: value
            for key, value in vault_values.items()
            if key in model_fields and key not in current_keys
        }


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
