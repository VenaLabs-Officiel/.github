#!/usr/bin/env python3
"""Contrôle YAML des runners, permissions effectives et actions épinglées."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys

import yaml


class WorkflowLoader(yaml.SafeLoader):
    pass


# YAML 1.2 : « on » est une clé de workflow, pas un booléen YAML 1.1.
WorkflowLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:bool']
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$', re.I), list('tTfF'))


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'clé YAML dupliquée : {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
SHA = re.compile(r'^[0-9a-f]{40}$')


def load_exceptions(path, repository):
    today = dt.date.today()
    result = []
    for item in json.loads(path.read_text(encoding='utf-8')).get('exceptions', []):
        if item.get('repository') != repository:
            continue
        if dt.date.fromisoformat(item['expires']) < today:
            raise ValueError(f"exception expirée : {item['workflow']} / {item['job']}")
        if not item.get('reason', '').strip():
            raise ValueError('exception sans justification')
        result.append(item)
    return result


def action_error(reference):
    if not isinstance(reference, str):
        return 'référence uses invalide'
    if reference.startswith('./'):
        return None
    if reference.startswith('docker://'):
        if not re.search(r'@sha256:[0-9a-f]{64}$', reference):
            return 'action Docker sans digest'
        return None
    parts = reference.rsplit('@', 1)
    if len(parts) != 2 or '/' not in parts[0] or not SHA.fullmatch(parts[1]):
        return 'action distante non épinglée par SHA'
    return None


def scan_workflow(path, exceptions):
    try:
        workflow = yaml.load(path.read_text(encoding='utf-8-sig'), Loader=WorkflowLoader)
        if not isinstance(workflow, dict) or not isinstance(workflow.get('jobs'), dict) or not workflow['jobs']:
            return [f'{path.name}: aucun job valide']
        errors = []
        for name, job in workflow['jobs'].items():
            prefix = f'{path.name}:{name}'
            if not isinstance(job, dict):
                errors.append(f'{prefix}: job invalide')
                continue
            exception = next((x for x in exceptions if x.get('workflow') == path.name and x.get('job') == name), {})
            permissions = job.get('permissions', workflow.get('permissions', {}))
            if permissions == 'write-all':
                errors.append(f'{prefix}: write-all interdit')
            elif isinstance(permissions, dict):
                allowed = exception.get('allow_write_permissions', [])
                for scope, level in permissions.items():
                    if level == 'write' and scope not in allowed:
                        errors.append(f'{prefix}: permission {scope}: write non autorisée')
            elif permissions != 'read-all':
                errors.append(f'{prefix}: permissions dynamiques ou invalides')
            if 'uses' in job:
                error = action_error(job['uses'])
                if error:
                    errors.append(f'{prefix}: {error}')
                continue
            timeout = job.get('timeout-minutes')
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
                errors.append(f'{prefix}: timeout-minutes doit être compris entre 1 et 120')
            runner = job.get('runs-on')
            if isinstance(runner, dict):
                runner = runner.get('labels')
            labels = runner if isinstance(runner, list) else [runner]
            shared = 'self-hosted' in labels and 'venalabs-ci' in labels
            approved = runner in exception.get('allowed_hosted_labels', []) if isinstance(runner, str) else False
            dedicated = labels == exception.get('allowed_self_hosted_labels')
            if not shared and not approved and not dedicated:
                errors.append(f'{prefix}: runner absent, dynamique ou sans exception exacte')
            if runner == 'ubuntu-slim' and isinstance(timeout, int) and timeout > 15:
                errors.append(f'{prefix}: ubuntu-slim limité à 15 minutes')
            for step in job.get('steps', []):
                if isinstance(step, dict) and 'uses' in step:
                    error = action_error(step['uses'])
                    if error:
                        errors.append(f'{prefix}: {error}')
        return errors
    except (yaml.YAMLError, ValueError, TypeError) as exc:
        return [f'{path.name}: YAML invalide ({exc})']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    parser.add_argument('--workflows', type=Path, required=True)
    parser.add_argument('--exceptions', type=Path, required=True)
    args = parser.parse_args()
    try:
        exceptions = load_exceptions(args.exceptions, args.repository)
    except (KeyError, ValueError, OSError) as exc:
        print(f'runner-policy: configuration invalide : {exc}', file=sys.stderr)
        return 1
    files = sorted(args.workflows.glob('*.yml')) + sorted(args.workflows.glob('*.yaml'))
    errors = [error for path in files for error in scan_workflow(path, exceptions)]
    if not files:
        errors.append('aucun workflow à contrôler')
    for error in errors:
        print(f'::error::{error}')
    print(f'runner-policy: {len(files)} workflow(s), {len(errors)} violation(s)')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
