"""Source contract checks for the real Rust allowlist, UI and Python dispatch."""
import ast
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]


def bridge_methods():
    source = (ROOT / 'src-tauri/src/main.rs').read_text()
    match = re.search(r'const ALLOWED:\s*&\[&str\]\s*=\s*&\[(.*?)\];', source, re.S)
    assert match is not None, 'Could not inspect the Rust RPC allowlist'
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def backend_methods():
    tree = ast.parse((ROOT / 'backend/narratorverse/main.py').read_text())
    backend = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Backend')
    handle = next(node for node in backend.body if isinstance(node, ast.FunctionDef) and node.name == 'handle')
    methods = set()
    for node in ast.walk(handle):
        if not (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                and node.left.id == 'method' and len(node.ops) == 1):
            continue
        value = node.comparators[0]
        if isinstance(node.ops[0], ast.Eq) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            methods.add(value.value)
        elif isinstance(node.ops[0], ast.In) and isinstance(value, (ast.Tuple, ast.List)):
            methods.update(item.value for item in value.elts
                           if isinstance(item, ast.Constant) and isinstance(item.value, str))
    assert 'audio_targets' in methods and 'shutdown' in methods
    return methods


def test_rust_bridge_allows_public_backend_methods_but_not_shutdown():
    # shutdown belongs to the process owner, not arbitrary frontend requests.
    assert bridge_methods() == backend_methods() - {'shutdown'}


def test_literal_frontend_requests_are_allowed_by_bridge():
    source = (ROOT / 'src/App.svelte').read_text()
    methods = set(re.findall(r"\b(?:action|rpc)(?:<[^>\n]+>)?\(\s*'([a-z_]+)'", source))
    assert 'audio_targets' in methods
    assert methods <= bridge_methods()


@pytest.mark.parametrize('method', ['shutdown', 'arbitrary_method', 'set_master_volume', ''])
def test_bridge_remains_restricted(method):
    source = (ROOT / 'src-tauri/src/main.rs').read_text()
    assert 'if !ALLOWED.contains(&method.as_str())' in source
    assert method not in bridge_methods()