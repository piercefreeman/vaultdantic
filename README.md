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


class ExampleSettings(BaseSettings, VaultMixin):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="EXAMPLE_",
        extra="ignore",
    )
    model_vault_config = OnePasswordConfigDict(
        vault="Engineering",
        entry="example-service",
    )

    api_token: SecretStr
    workspace_id: str
```

When `ExampleSettings()` is created, values are resolved in this order:

1. `pydantic-settings` loads normal sources first (`__init__` kwargs, environment, `.env`, and file secrets).  
2. If required fields are still missing, `OnePasswordConfigDict.get_vars()` is called and only missing keys are filled from the vault entry.  
3. Any key already provided by earlier sources keeps precedence over vault values, then the final model is validated.

Vault field labels should use env-style keys (for example `EXAMPLE_API_TOKEN`, not `api_token`).

## Vault Providers

| Provider | Config Class |
| --- | --- |
| 1Password | `OnePasswordConfigDict` |

## CLI

We also provide convenience methods to sync your vaults _into_ an .env file, to make it easier to sync to a remote host or use in Docker. Sync all discovered vault values into `.env`:

```bash
uv run sync-vault-to-env
```

This will write your credentials in a special managed-by-vaultdantic section. We will overwrite this section on any subsequent syncs so we recommend leaving it alone.

```dotenv
# start managed by vaultdantic
...
# end managed by vaultdantic
```

## Development

```bash
make sync
make lint
make test
make build
```
