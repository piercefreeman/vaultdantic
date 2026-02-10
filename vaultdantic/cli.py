from __future__ import annotations

import argparse
import importlib
import inspect
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic_settings import BaseSettings

from vaultdantic.vaults.base import VaultConfigDict

START_MARKER = "# start managed by vaultdantic"
END_MARKER = "# end managed by vaultdantic"
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


@dataclass(slots=True)
class SyncResult:
    env_file: Path
    modules_loaded: int
    settings_models_found: int
    providers_queried: int
    variables_written: int
    import_errors: int


@dataclass(frozen=True, slots=True)
class _DiscoveredSettings:
    module_name: str
    qualname: str
    vault_config: VaultConfigDict


def sync_vault_to_env(
    project_root: Path,
    env_file: Path | None = None,
    fail_on_import_error: bool = True,
) -> SyncResult:
    project_root = project_root.resolve()
    output_env_file = _resolve_env_file(project_root=project_root, env_file=env_file)

    module_names = _discover_module_names(project_root)
    modules, import_errors = _load_modules(
        module_names=module_names,
        project_root=project_root,
        fail_on_import_error=fail_on_import_error,
    )

    discovered_settings = _discover_settings_modules(modules)
    merged_values, providers_queried = _collect_provider_values(discovered_settings)

    managed_block = _render_managed_block(merged_values)
    existing_contents = (
        output_env_file.read_text(encoding="utf-8") if output_env_file.exists() else ""
    )
    output_contents = _upsert_managed_block(existing_contents, managed_block)

    output_env_file.parent.mkdir(parents=True, exist_ok=True)
    output_env_file.write_text(output_contents, encoding="utf-8")

    return SyncResult(
        env_file=output_env_file,
        modules_loaded=len(modules),
        settings_models_found=len(discovered_settings),
        providers_queried=providers_queried,
        variables_written=len(merged_values),
        import_errors=len(import_errors),
    )


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync-vault-to-env",
        description=(
            "Import project modules, discover vault settings providers, and sync provider values "
            "into a managed section of an env file."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root to scan for Python modules (default: current directory).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Env file path to write (default: .env at the project root).",
    )
    parser.add_argument(
        "--allow-import-errors",
        action="store_true",
        help="Continue on module import errors and sync values from successfully imported modules.",
    )
    args = parser.parse_args(argv)

    try:
        result = sync_vault_to_env(
            project_root=args.project_root,
            env_file=args.env_file,
            fail_on_import_error=not args.allow_import_errors,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if result.import_errors:
        print(
            f"Warning: skipped {result.import_errors} module import error(s).",
            file=sys.stderr,
        )
    print(
        f"Wrote {result.variables_written} variable(s) from {result.providers_queried} provider(s) "
        f"across {result.settings_models_found} settings model(s) to {result.env_file}."
    )
    return 0


def main() -> None:
    raise SystemExit(cli())


def _resolve_env_file(project_root: Path, env_file: Path | None) -> Path:
    target = env_file if env_file is not None else Path(".env")
    if target.is_absolute():
        return target
    return (project_root / target).resolve()


def _discover_module_names(project_root: Path) -> list[str]:
    module_names: set[str] = set()
    src_root = project_root / "src"
    roots: list[Path] = [project_root]
    if src_root.is_dir():
        roots.append(src_root)

    for root in roots:
        for file_path in root.rglob("*.py"):
            relative = file_path.relative_to(root)
            if _should_skip_path(relative):
                continue
            if (
                root == project_root
                and relative.parts
                and relative.parts[0] == "src"
                and src_root.is_dir()
            ):
                continue

            module_name = _module_name_from_path(relative)
            if module_name is not None:
                module_names.add(module_name)

    return sorted(module_names)


def _load_modules(
    module_names: Sequence[str],
    project_root: Path,
    fail_on_import_error: bool,
) -> tuple[list[ModuleType], list[tuple[str, Exception]]]:
    import_paths = [str(project_root)]
    src_root = project_root / "src"
    if src_root.is_dir():
        import_paths.append(str(src_root))

    previous_sys_path = list(sys.path)
    for import_path in reversed(import_paths):
        if import_path not in sys.path:
            sys.path.insert(0, import_path)

    importlib.invalidate_caches()

    loaded_modules: list[ModuleType] = []
    import_errors: list[tuple[str, Exception]] = []

    try:
        for module_name in module_names:
            try:
                loaded_modules.append(_import_module(module_name, project_root))
            except Exception as exc:
                import_errors.append((module_name, exc))

        if import_errors and fail_on_import_error:
            errors = "\n".join(f"- {name}: {exc!r}" for name, exc in import_errors)
            raise RuntimeError(f"Failed to import project modules:\n{errors}")
        return loaded_modules, import_errors
    finally:
        sys.path = previous_sys_path


def _import_module(module_name: str, project_root: Path) -> ModuleType:
    existing_module = sys.modules.get(module_name)
    if existing_module is not None:
        module_file = getattr(existing_module, "__file__", None)
        if isinstance(module_file, str):
            if not _is_subpath(Path(module_file).resolve(), project_root):
                del sys.modules[module_name]
            else:
                return importlib.reload(existing_module)

    return importlib.import_module(module_name)


def _discover_settings_modules(modules: Sequence[ModuleType]) -> list[_DiscoveredSettings]:
    discovered: list[_DiscoveredSettings] = []
    seen: set[tuple[str, str]] = set()

    for module in modules:
        for _, class_obj in inspect.getmembers(module, inspect.isclass):
            if class_obj.__module__ != module.__name__:
                continue
            if not issubclass(class_obj, BaseSettings):
                continue

            vault_config = getattr(class_obj, "model_vault_config", None)
            if not isinstance(vault_config, VaultConfigDict):
                continue

            key = (class_obj.__module__, class_obj.__qualname__)
            if key in seen:
                continue
            seen.add(key)
            discovered.append(
                _DiscoveredSettings(
                    module_name=class_obj.__module__,
                    qualname=class_obj.__qualname__,
                    vault_config=vault_config,
                )
            )

    discovered.sort(key=lambda item: (item.module_name, item.qualname))
    return discovered


def _collect_provider_values(
    discovered_settings: Sequence[_DiscoveredSettings],
) -> tuple[dict[str, str], int]:
    merged_values: dict[str, str] = {}
    seen_provider_ids: set[int] = set()
    providers_queried = 0

    for setting in discovered_settings:
        provider = setting.vault_config
        provider_id = id(provider)
        if provider_id in seen_provider_ids:
            continue
        seen_provider_ids.add(provider_id)
        providers_queried += 1

        for key, value in provider.get_vars().items():
            merged_values[str(key)] = _to_env_string(value)

    return merged_values, providers_queried


def _render_managed_block(values: Mapping[str, str]) -> str:
    lines = [START_MARKER]
    for key in sorted(values):
        lines.append(f"{key}={_quote_env_value(values[key])}")
    lines.append(END_MARKER)
    return "\n".join(lines)


def _upsert_managed_block(existing: str, block: str) -> str:
    if START_MARKER in existing and END_MARKER not in existing:
        raise RuntimeError(
            f"Found '{START_MARKER}' without a matching '{END_MARKER}'. Resolve manually and retry."
        )

    pattern = re.compile(rf"(?ms)^{re.escape(START_MARKER)}\n.*?^{re.escape(END_MARKER)}\s*\n?")
    without_managed = pattern.sub("", existing).rstrip()
    if without_managed:
        return f"{without_managed}\n\n{block}\n"
    return f"{block}\n"


def _should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES or part.startswith(".") for part in path.parts[:-1])


def _module_name_from_path(path: Path) -> str | None:
    parts = list(path.parts)
    filename = parts[-1]

    if filename == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = filename.removesuffix(".py")

    if not parts:
        return None
    if any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _quote_env_value(value: str) -> str:
    if not value:
        return '""'

    if "\n" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'

    needs_quotes = any(char.isspace() for char in value) or any(
        char in value for char in ['"', "'", "#"]
    )
    if needs_quotes:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _to_env_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _is_subpath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
