# vaultdantic

`vaultdantic` extends `pydantic-settings` with a vault-backed fallback source.

If you're already in the pydantic ecosystem, `pydantic-settings` makes it easy to specify your environment configuration as env files and load them at runtime. When you're working on a remote production app, you probably only need these global environment keys. But when you're working locally on side projects, it's way more convenient to store your environment parameters in a vault like 1Password. This lets you delete the contents of your machine and restore your secrets with a simple vault pull.

`BaseSettings` inputs continue to win in normal priority order (`init` args, env vars, `.env`, file
secrets), and the vault provider is only queried when required fields are still missing.

## Usage

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from vaultdantic import OnePasswordConfigDict, VaultMixin


class FrameioSettings(BaseSettings, VaultMixin):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FRAMEIO_",
        extra="ignore",
    )
    model_vault_config = OnePasswordConfigDict(
        vault="Engineering",
        entry="frameio-service",
    )

    token: SecretStr
    destination_id: str
```

## Development

```bash
make sync
make lint
make test
make build
```
