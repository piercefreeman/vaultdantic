#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SECTION_PATTERN = re.compile(r"^\s*\[(?P<section>[^\]]+)\]\s*(?:#.*)?$")
VERSION_PATTERN = re.compile(r"""^(\s*version\s*=\s*)(["'])([^"']*)(["'])(\s*(?:#.*)?)$""")


def normalize_tag(tag: str) -> str:
    normalized = tag.strip()
    if normalized.startswith("refs/tags/"):
        normalized = normalized.removeprefix("refs/tags/")

    if normalized.startswith("v"):
        normalized = normalized[1:]

    if not normalized:
        raise ValueError(f"Tag {tag!r} does not contain a version.")
    if any(ch.isspace() for ch in normalized):
        raise ValueError(f"Tag {tag!r} contains whitespace, which is not valid for a version.")
    if not re.fullmatch(r"[0-9A-Za-z.+!_-]+", normalized):
        raise ValueError(f"Tag {tag!r} contains unsupported characters for a version.")
    return normalized


def update_pyproject_version(pyproject_path: Path, version: str) -> tuple[str | None, bool]:
    content = pyproject_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    project_start: int | None = None
    project_end = len(lines)
    for index, line in enumerate(lines):
        section_match = SECTION_PATTERN.match(line.strip())
        if not section_match:
            continue

        section = section_match.group("section").strip()
        if section == "project":
            project_start = index
            continue
        if project_start is not None:
            project_end = index
            break

    if project_start is None:
        raise ValueError("Could not find a [project] section in pyproject.toml.")

    for index in range(project_start + 1, project_end):
        line = lines[index]
        if not re.match(r"^\s*version\s*=", line):
            continue

        version_match = VERSION_PATTERN.match(line.rstrip("\r\n"))
        if not version_match:
            raise ValueError(
                f"Found [project].version line but could not parse expected quoted value: {line.strip()!r}"
            )

        old_version = version_match.group(3)
        line_ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        prefix = version_match.group(1)
        suffix = version_match.group(5)
        lines[index] = f'{prefix}"{version}"{suffix}{line_ending}'
        pyproject_path.write_text("".join(lines), encoding="utf-8")
        return old_version, old_version != version

    line_ending = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    lines.insert(project_start + 1, f'version = "{version}"{line_ending}')
    pyproject_path.write_text("".join(lines), encoding="utf-8")
    return None, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update [project].version in pyproject.toml to match a Git tag."
    )
    parser.add_argument(
        "--tag",
        help="Release tag value (for example: v1.2.3). Defaults to GITHUB_REF_NAME.",
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tag = args.tag or os.getenv("GITHUB_REF_NAME")
    if not tag:
        print("Missing --tag and GITHUB_REF_NAME is not set.", file=sys.stderr)
        return 2

    version = normalize_tag(tag)
    pyproject_path = Path(args.pyproject)
    if not pyproject_path.exists():
        print(f"pyproject.toml not found: {pyproject_path}", file=sys.stderr)
        return 2

    try:
        old_version, changed = update_pyproject_version(pyproject_path, version)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if changed and old_version is not None:
        print(f"Updated {pyproject_path}: {old_version} -> {version}")
    elif changed:
        print(f"Set {pyproject_path} version to {version}")
    else:
        print(f"{pyproject_path} already set to {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
