"""Workspace-root paths and a small structured preflight report."""
from pathlib import Path
import hashlib
import yaml


def load_yaml(path):
    with Path(path).open(encoding='utf-8') as f:
        value = yaml.safe_load(f)
    if not isinstance(value, dict):
        raise ValueError('CONFIG_NOT_MAPPING')
    return value


def resolve_path(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError('PATH_MISSING')
    p = Path(value).expanduser()
    return p.resolve() if p.is_absolute() else (Path(root).resolve() / p).resolve()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def issue(code, field, message):
    return {'code': code, 'field': field, 'message': message}
