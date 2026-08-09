#!/usr/bin/env python3
"""Contrôle central minimal des workflows GitHub Actions VenaLabs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HOSTED_RE = re.compile(r"\b(?:ubuntu|windows|macos)-(?:latest|[0-9][A-Za-z0-9.-]*)\b")
REMOTE_ACTION_RE = re.compile(r"^([^\s#]+/[^\s#]+)@([^\s#]+)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
WRITE_RE = re.compile(r"^\s{4,}([A-Za-z0-9_-]+):\s*write\s*(?:#.*)?$")


def load_exceptions(path: Path, repository: str) -> list[dict[str, object]]:
    today = dt.date.today()
    result: list[dict[str, object]] = []
    for item in json.loads(path.read_text(encoding="utf-8")).get("exceptions", []):
        if item.get("repository") != repository:
            continue
        expires = dt.date.fromisoformat(str(item["expires"]))
        if expires < today:
            raise ValueError(
                f"exception expirée pour {item.get('workflow')} / {item.get('job')}: {expires}"
            )
        if not str(item.get("reason", "")).strip():
            raise ValueError("une exception doit porter une justification")
        result.append(item)
    return result


def exception_for(
    exceptions: list[dict[str, object]], workflow: str, job: str | None
) -> dict[str, object]:
    for item in exceptions:
        if item.get("workflow") == workflow and item.get("job") == job:
            return item
    return {}


def scan_workflow(path: Path, exceptions: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    workflow = path.name
    current_job: str | None = None
    in_jobs = False

    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line == "jobs:":
            in_jobs = True
            current_job = None
            continue
        if in_jobs and line and not line.startswith((" ", "#")):
            in_jobs = False
            current_job = None
        if in_jobs:
            match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
            if match:
                current_job = match.group(1)

        exception = exception_for(exceptions, workflow, current_job)
        if "runs-on:" in line:
            if HOSTED_RE.search(line):
                if not exception.get("allow_github_hosted"):
                    errors.append(f"{workflow}:{number}: runner GitHub-hosted interdit")
            elif "self-hosted" not in line:
                errors.append(f"{workflow}:{number}: runs-on doit contenir self-hosted")

        uses = re.match(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", line)
        if uses and not uses.group(1).startswith(("./", "docker://")):
            remote = REMOTE_ACTION_RE.match(uses.group(1))
            if not remote or not SHA_RE.fullmatch(remote.group(2)):
                errors.append(f"{workflow}:{number}: action distante non épinglée par SHA")

        write = WRITE_RE.match(line)
        if write:
            allowed = exception.get("allow_write_permissions", [])
            if write.group(1) not in allowed:
                errors.append(
                    f"{workflow}:{number}: permission {write.group(1)}: write non autorisée"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflows", type=Path, required=True)
    parser.add_argument("--exceptions", type=Path, required=True)
    args = parser.parse_args()

    try:
        exceptions = load_exceptions(args.exceptions, args.repository)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"runner-policy: configuration invalide: {exc}", file=sys.stderr)
        return 1

    files = sorted(args.workflows.glob("*.yml")) + sorted(args.workflows.glob("*.yaml"))
    errors = [error for path in files for error in scan_workflow(path, exceptions)]
    for error in errors:
        print(f"::error::{error}")
    if errors:
        print(f"runner-policy: {len(errors)} violation(s)", file=sys.stderr)
        return 1
    print(f"runner-policy: {len(files)} workflow(s) conformes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
