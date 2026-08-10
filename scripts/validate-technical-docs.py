#!/usr/bin/env python3
"""Validate source-derived AVAROS technical handover invariants.

This script uses only the Python standard library. It intentionally parses the
source rather than importing AVAROS runtime modules, so it can run before Docker
images or Python application dependencies are installed.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HANDOVER = DOCS / "RENERYO-TECHNICAL-HANDOVER.md"
API_REFERENCE = DOCS / "AVAROS-API-REFERENCE.md"
INTENT_REFERENCE = DOCS / "INTENTS-AND-DIALOGUE.md"

REQUIRED_DOCS = (
    HANDOVER,
    DOCS / "SYSTEM-ARCHITECTURE.md",
    API_REFERENCE,
    INTENT_REFERENCE,
    DOCS / "DATA-LIFECYCLE.md",
    DOCS / "ALERTS-AND-NOTIFICATIONS.md",
)


def _failures_for_required_files() -> list[str]:
    return [f"missing required document: {path.relative_to(ROOT)}" for path in REQUIRED_DOCS if not path.is_file()]


def _class_string_values(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values: set[str] = set()
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                    values.add(statement.value.value)
            return values
    raise ValueError(f"class {class_name} not found in {path}")


def _assignment_node(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    raise ValueError(f"assignment {name} not found in {path}")


def _intent_identifiers() -> set[str]:
    path = ROOT / "skill" / "_intent_maps.py"
    metric_map = _assignment_node(path, "INTENT_METRIC_MAP")
    non_kpi_map = _assignment_node(path, "NON_KPI_INTENT_MAP")
    identifiers: set[str] = set()

    if not isinstance(metric_map, ast.Dict) or not isinstance(non_kpi_map, (ast.Tuple, ast.List)):
        raise ValueError("unexpected intent map AST shape")

    for key in metric_map.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            identifiers.add(key.value)
    for item in non_kpi_map.elts:
        if isinstance(item, (ast.Tuple, ast.List)) and item.elts:
            value = item.elts[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                identifiers.add(value.value.removesuffix(".intent"))
    return identifiers


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        function_name = value.func.id if isinstance(value.func, ast.Name) else ""
        if function_name != "APIRouter":
            continue
        prefix = ""
        for keyword in value.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                prefix = str(keyword.value.value)
        for target in targets:
            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix
    return prefixes


def _source_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = {("GET", "/health")}
    method_names = {"get", "post", "put", "delete", "patch", "options", "websocket"}
    for path in sorted((ROOT / "web-ui" / "routers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        prefixes = _router_prefixes(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                owner = decorator.func.value
                if not isinstance(owner, ast.Name) or owner.id not in prefixes:
                    continue
                method = decorator.func.attr.lower()
                if method not in method_names or not decorator.args:
                    continue
                route_arg = decorator.args[0]
                if not isinstance(route_arg, ast.Constant) or not isinstance(route_arg.value, str):
                    continue
                http_method = "WEBSOCKET" if method == "websocket" else method.upper()
                routes.add((http_method, f"{prefixes[owner.id]}{route_arg.value}"))
    return routes


def _failures_for_metrics() -> list[str]:
    metrics = _class_string_values(ROOT / "skill" / "domain" / "models.py", "CanonicalMetric")
    text = HANDOVER.read_text(encoding="utf-8")
    return [f"canonical metric missing from handover: {metric}" for metric in sorted(metrics) if f"`{metric}`" not in text]


def _failures_for_intents() -> list[str]:
    identifiers = _intent_identifiers()
    text = INTENT_REFERENCE.read_text(encoding="utf-8")
    failures = [f"runtime intent missing from intent reference: {name}" for name in sorted(identifiers) if name not in text]
    intent_file_count = len(list((ROOT / "skill" / "locale" / "en-us").glob("*.intent")))
    if len(identifiers) != intent_file_count:
        failures.append(
            f"runtime intent map/file mismatch: map={len(identifiers)} files={intent_file_count}"
        )
    return failures


def _failures_for_routes() -> list[str]:
    text = API_REFERENCE.read_text(encoding="utf-8")
    failures: list[str] = []
    for method, path in sorted(_source_routes()):
        table_pattern = rf"\|\s*{re.escape(method)}\s*\|\s*`{re.escape(path)}`\s*\|"
        if re.search(table_pattern, text) is None:
            failures.append(f"route missing from API reference table: {method} {path}")
    return failures


def _failures_for_handover_links() -> list[str]:
    text = HANDOVER.read_text(encoding="utf-8")
    failures: list[str] = []
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", text):
        if "://" in target or target.startswith("mailto:"):
            continue
        resolved = HANDOVER.parent / target
        if not resolved.exists():
            failures.append(f"broken handover link: {target}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_failures_for_required_files())
    if not failures:
        failures.extend(_failures_for_metrics())
        failures.extend(_failures_for_intents())
        failures.extend(_failures_for_routes())
        failures.extend(_failures_for_handover_links())

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    print(
        "Technical docs verified: "
        f"{len(REQUIRED_DOCS)} documents, "
        f"{len(_class_string_values(ROOT / 'skill' / 'domain' / 'models.py', 'CanonicalMetric'))} metrics, "
        f"{len(_intent_identifiers())} intents, "
        f"{len(_source_routes())} routes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
