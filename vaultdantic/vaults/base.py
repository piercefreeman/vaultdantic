from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict


class VaultConfigDict(BaseModel, ABC):
    """Base model for vault provider configuration."""

    model_config = ConfigDict(extra="forbid")

    @abstractmethod
    def get_vars(self) -> Mapping[str, Any]:
        """Return settings key/value pairs from the configured provider."""
