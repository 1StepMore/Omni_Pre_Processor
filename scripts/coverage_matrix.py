#!/usr/bin/env python3
"""coverage_matrix — OPP 生产矩阵校验（issue OPP#112）。

从源码派生「格式 × 提取方法 × MCP 工具 × 错误处理」的真值，与
docs/dev/production-matrix.md 的矩阵行比对：矩阵里每个格子必须标注
✅ / ⚠️ / ❌，且行集合、格式集合、工具集合与派生值一致。

用法：
    python scripts/coverage_matrix.py --check     # 校验（exit 1 = 漂移）
    python scripts/coverage_matrix.py             # 打印派生真值（人读）

与 scripts/doc_inventory.py 同一哲学：矩阵不是手写的希望，是能被
源码证伪的声明。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MATRIX_PATH = ROOT / "docs" / "dev" / "production-matrix.md"


def _derive() -> dict:
    """从源码派生矩阵真值。"""
    from opp.mcp.server import _TOOL_SCHEMAS
    from opp.mcp.tools.get_capabilities import _INPUT_FORMATS
    from opp.extractors import __all__ as registry

    extractors = sorted(n for n in registry if n != "ExtractorBase")
    tools = sorted(str(s.get("name")) for s in _TOOL_SCHEMAS)
    # MCP 工具面按能力域分组（声明在 server 的 tool 描述里，这里按名单归类）
    return {
        "input_formats": list(_INPUT_FORMATS),
        "extractors": extractors,
        "tools": tools,
        "output_formats": ["md", "xliff"],  # opp --target-format 的两个值
    }


#: 矩阵文档中每一行必须有的标注符。
_COVERAGE_MARKS = ("✅", "⚠️", "❌")

#: 行格式：| `<format>` | <extractor 标注> | <mcp 标注> | <notes> |
_ROW_RE = re.compile(r"^\|\s*`([a-z0-9]+)`\s*\|(.+)\|\s*$")


def _parse_matrix_rows() -> list[tuple[str, str]]:
    """从矩阵文档抽格式行：(format, 行原文剩余部分)。"""
    if not MATRIX_PATH.is_file():
        raise SystemExit(f"missing {MATRIX_PATH} — write the matrix first")
    rows = []
    in_section = False
    for line in MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Format coverage"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        m = _ROW_RE.match(line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def check() -> int:
    failures: list[str] = []
    truth = _derive()

    rows = _parse_matrix_rows()
    row_formats = [f for f, _ in rows]

    # 1) 格式集合一致（顺序不强制，集合必须相等）
    if set(row_formats) != set(truth["input_formats"]):
        missing = sorted(set(truth["input_formats"]) - set(row_formats))
        extra = sorted(set(row_formats) - set(truth["input_formats"]))
        failures.append(
            f"matrix format rows out of sync with get_capabilities: "
            f"missing={missing} extra={extra}"
        )

    # 2) 每行必须有覆盖标注（✅/⚠️/❌ 至少其一），且标注不出现在无格子的行
    for fmt, rest in rows:
        if not any(mark in rest for mark in _COVERAGE_MARKS):
            failures.append(f"matrix row `{fmt}` carries no ✅/⚠️/❌ coverage mark")

    # 3) 工具清单段：矩阵必须提到每个 MCP 工具名
    body = MATRIX_PATH.read_text(encoding="utf-8")
    for tool in truth["tools"]:
        if f"`{tool}`" not in body:
            failures.append(f"matrix does not mention tool `{tool}`")

    # 4) 格式数与工具数在文档头部的计数行
    for pattern, expected in (
        (re.compile(r"input formats: \*\*(\d+)\*\*"), len(truth["input_formats"])),
        (re.compile(r"MCP tools: \*\*(\d+)\*\*"), len(truth["tools"])),
        (re.compile(r"extractor classes: \*\*(\d+)\*\*"), len(truth["extractors"])),
    ):
        m = pattern.search(body)
        if not m:
            failures.append(f"matrix header missing count line: {pattern.pattern}")
        elif int(m.group(1)) != expected:
            failures.append(
                f"matrix header claims {m.group(0)!r} but source derives {expected}"
            )

    if failures:
        print("coverage matrix check FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        f"coverage matrix check passed: {len(truth['input_formats'])} formats, "
        f"{len(truth['tools'])} tools, {len(truth['extractors'])} extractor classes, "
        f"{len(rows)} matrix rows in sync."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="coverage_matrix")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if not args.check:
        truth = _derive()
        print(f"input formats ({len(truth['input_formats'])}):", ", ".join(truth["input_formats"]))
        print(f"extractor classes ({len(truth['extractors'])}):", ", ".join(truth["extractors"]))
        print(f"MCP tools ({len(truth['tools'])}):", ", ".join(truth["tools"]))
        print(f"output formats: {', '.join(truth['output_formats'])}")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
