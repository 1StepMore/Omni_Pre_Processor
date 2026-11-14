# AGENTS.md — Omni_Pre_Processor (OPP)

Developer + agent context for the **OPP** sub-repo. The suite-level
[suite-level AGENTS.md](https://github.com/1StepMore/e2e-test-suite/blob/main/AGENTS.md) covers cross-module
orchestration (OPP → OL → ORF); this file is for working **inside**
OPP.

> OPP is the first step of the Omni Suite pipeline. It extracts
> documents (DOCX/PPTX/PDF/HTML/EPUB/EML/MSG/images/…) into
> standardized **Markdown + XLIFF + skeleton.zip** for downstream
> translation and backfill. It accepts **16 input formats** and exposes
> **9 MCP tools**.

> **Prerequisite:** Python >= 3.13. Verify with `python3 --version`.

This file is an **index + invariants** file (≤200 lines, OPP#119): detail
lives in `docs/dev/*.md` and `docs/API.md`, not here.

## Quick start

```bash
# Install
bash scripts/setup_dev.sh

# CLI: extract a DOCX
opp document.docx --target-format both --output-dir /tmp/out

# CLI: extract with explicit language pair
opp document.docx --target-format both --source-lang en --target-lang zh

# MCP server (stdio)
opp mcp             # or: python -m opp.mcp.server

# Tests
make test           # runs uv run pytest tests/ -v
```

## Non-negotiable invariants / taboos

- **MCP path security is fail-closed.** `OPP_MCP_ALLOWED_DIRS` is
  **required**; unset ⇒ the server refuses to start
  (`ValueError("allowed_directories cannot be empty")`). It is NOT
  `OPP_ALLOWED_DIRECTORIES` (CLI-only). Never loosen a rejected path
  request — fix the allowlist. Full model:
  [path-config.md](docs/dev/path-config.md).
- **PDF → XLIFF is intentionally blocked.** `generate_xliff` raises on
  PDF input; extract PDF → MD instead. Detail:
  [xliff-schema.md](docs/dev/xliff-schema.md#pdf--xliff-limitation).
- **MSG → prefer EML.** MSG input needs the optional `extract-msg`
  package; MSG *output* requires commercial Aspose.Email, so use `.eml`
  (suite-level rule). Detail: [extractors.md](docs/dev/extractors.md).
- **FAKE_LLM rules.** `OMNI_TEST_FAKE_LLM=1` is the deterministic mock
  seam: allowed for CLI smoke/contract runs and unit tests, **forbidden
  as human-quality validation evidence** (a fallback-active run is
  `invalid`). Detail: [gotchas.md](docs/dev/gotchas.md).
- **pandoc dependency.** `--style-map` is pandoc-based; pandoc ships via
  `pypandoc-binary` (auto-installed). Detail:
  [cli-reference.md](docs/dev/cli-reference.md).
- **Do not double-handle images.** `ImageData.is_inline_in_md` must be
  set correctly; `MarkdownGenerator` dedup depends on it (E2E-75).
  Detail: [image-pipeline.md](docs/dev/image-pipeline.md).

## MCP tools (9 total)

`extract_document`, `batch_extract`, `detect_format_tool`,
`generate_markdown`, `generate_xliff`, `save_skeleton`, `validate_xliff`,
`get_capabilities`, `ping`.

Full per-tool parameters: [`docs/API.md`](docs/API.md). The suite-level
[agent-pipeline-guide.md](https://github.com/1StepMore/e2e-test-suite/blob/main/docs/agent-pipeline-guide.md)
covers server/tool inventory and namespacing.

## Detail index (moved out of AGENTS.md, OPP#119)

| Topic | Detail doc |
|---|---|
| Source tree, extractors, adding a new format | [source-layout.md](docs/dev/source-layout.md), [extractors.md](docs/dev/extractors.md) |
| MCP tool purpose table | [mcp-tools.md](docs/dev/mcp-tools.md) |
| Image extraction / dedup (E2E-15, E2E-75) | [image-pipeline.md](docs/dev/image-pipeline.md) |
| CLI command + flag table | [cli-reference.md](docs/dev/cli-reference.md) |
| XLIFF output schema, PDF → XLIFF limitation | [xliff-schema.md](docs/dev/xliff-schema.md) |
| env vars, MCP path config, PathValidator | [path-config.md](docs/dev/path-config.md) |
| skeleton.zip preservation | [skeleton.md](docs/dev/skeleton.md) |
| Known issues / gotchas (E2E-81/82, `.url`) | [gotchas.md](docs/dev/gotchas.md) |
| Tests, coverage, key regression files | [tests.md](docs/dev/tests.md) |
| `--target-format` selection guide | [target-format.md](docs/dev/target-format.md) |
| Validation (in-repo scenarios, coverage) | [validation.md](docs/dev/validation.md) |

## Pointers to the suite-level docs

- Cross-module orchestration: [AGENTS.md](https://github.com/1StepMore/e2e-test-suite/blob/main/AGENTS.md)
- Doc architecture playbook (six-repo synced copy, hash-pinned; e2e-test-suite#254): [`docs/dev/agent-era-doc-architecture.md`](docs/dev/agent-era-doc-architecture.md)
- MCP tool full parameter reference: [`docs/API.md`](docs/API.md)
- Pre-commit hooks: [.pre-commit-config.yaml](https://github.com/1StepMore/e2e-test-suite/blob/main/.pre-commit-config.yaml)
- Compatibility matrix: [COMPATIBILITY.md](https://github.com/1StepMore/e2e-test-suite/blob/main/COMPATIBILITY.md)
- OPP's own per-Agent skill files: `src/opp_agent/SKILL.md`
  (OpenCode) and `src/opp_hermes/SKILL.md` (Hermes) — supplementary
  tool-level references.

## Issue conventions

- **`pinned` = 常开索引件, not a to-do.** A pinned issue stays open as a
  roadmap pointer; do not close it, and do not consume it as a work item.
- **Cross-repo reference check.** `scripts/doc_inventory.py` verifies
  backticked paths in `README.md` / `AGENTS.md`. Write another repo's path
  with a `suite:` / `opp:` / `ol:` / `orf:` prefix; an unprefixed path must
  exist in this repo. The checker's shared block is byte-identical across the
  three module repos — change rule: `suite:docs/dev/doc-inventory-copies.md`.

## Role routing (A2 pointer model, 2026-11-08)

角色契约唯一事实源 = 套件根仓 `.agents/roles/`（coder/maintainer/tester/user，各 ≤30 行），本仓不设本地副本。
进入本仓的 agent：先读套件根 `AGENTS.md` 的 §0 安全与优先级 + 角色路由表，再按指派角色读对应契约；
期望映射层 = 套件根 `.agents/expectations/`，期望唯一事实源 = `scenarios/STANDARDS.md`（均 Owner 门禁）；standalone clone 按本仓 `docs/` 工作、边界按根 AGENTS.md §0 类推。

## 运行环境与门禁速查（harness 用 · 2026-11-14 核对）

| 项 | 内容 |
|:--|:--|
| 解释器 | uv 工程：`uv run` 优先；Windows 原生由**套件仓**的引导脚本建 `.venv_win`（脚本在本仓之外，不在本仓路径下） |
| 安装 | `uv sync --all-extras`（成员依赖以套件根 `uv.lock` 为准） |
| 必需密钥 | **无**（纯机械转换，不要给本仓加任何 key 相关代码或配置） |
| DoD 顺序 | `make test` → `make lint`（ruff）；三模块联合验证在套件仓跑 |
| 已知坑 | ① 改了成员依赖却不重建套件根 `uv.lock` ⇒ push CI 的 `validate` 会红（本地重建 lock 再提交）；② Windows 原生首跑缺 `omni-security` / `markdownify` 等包，套件 #320 在跟；③ 断言类测试严格，`AttributeError` 优先怀疑 API 变更而非测试写错 |
| 队列 | `gh issue list -l agent-ready --state open` |

> 本块是**本仓运行事实的唯一真身**（Owner 侧的通用执行提示词不写具体仓信息）。通用规则（边界 / 权限 / 合并判定）见 Owner 侧提示词，不入库。
