"""YAML loading that remembers line numbers, so findings can point at file:line."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class LineMap(dict):
    """Maps a dotted path (``fields.temperature_c.max``, ``grades.0.ni_pct``) to a 1-based line."""

    def line(self, *paths: str, default: int | None = 1) -> int | None:
        for p in paths:
            if p in self:
                return self[p]
            # walk up to the nearest parent we know
            parts = p.split(".")
            while parts:
                parts.pop()
                key = ".".join(parts)
                if key in self:
                    return self[key]
        return default


def _walk(node: yaml.Node, prefix: str, out: LineMap) -> None:
    if prefix:
        out.setdefault(prefix, node.start_mark.line + 1)
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            p = f"{prefix}.{k.value}" if prefix else str(k.value)
            out[p] = k.start_mark.line + 1
            _walk(v, p, out)
    elif isinstance(node, yaml.SequenceNode):
        for i, v in enumerate(node.value):
            _walk(v, f"{prefix}.{i}" if prefix else str(i), out)


def load_yaml(path: str | Path) -> tuple[Any, LineMap]:
    text = Path(path).read_text(encoding="utf-8")
    lines = LineMap()
    node = yaml.compose(text)
    if node is None:
        return None, lines
    _walk(node, "", lines)
    return yaml.safe_load(text), lines


def dump_yaml(data: Any, path: str | Path, header: str | None = None) -> None:
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    if header:
        text = "".join(f"# {h}\n" for h in header.strip().splitlines()) + text
    Path(path).write_text(text, encoding="utf-8")
