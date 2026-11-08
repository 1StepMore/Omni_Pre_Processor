# Inventory — Omni_Pre_Processor @ 015acc58a9d1f9f470fe6983fe122767d534e45e (2026-11-07)  SOURCE=LOCAL（§7.5）
| ID | 子系统 | 路径 | 类别 | 测试现状 | 文档现状 | CI 覆盖 | 判定依据 | 处置建议(A编号) |
|----|--------|------|------|----------|----------|---------|----------|----------------|
| S-01 | 抽取引擎 | src/opp/(16 输入格式 extractors) | 源码 | tests/ 1200+ | AGENTS.md(107行≤200✅)+README | ci.yml | 上游模块仓 | A2 路由指针/A10 核对 |
| S-02 | 测试 | tests/ | 测试 | 有 | — | ci.yml | 模块测试套件 | 不动 |
| S-03 | 文档 | docs/ + AGENTS.md + README | 文档 | — | suite: 跨仓引用前缀✅ | doc_inventory(本仓副本) | 跨仓检查 fail-closed(#253) | A13 副本同步(O-2) |
| S-04 | CI | .github/workflows/(ci.yml,publish.yml tracked + ?? pinned-guard.yml) | CI | — | — | 自身 | pinned-guard untracked→遗留 | A7: ci.yml 增一致性 job(O-2) |
| S-05 | 工程 | Makefile/pyproject.toml | CI | make test/lint 目标✅ | — | — | 参数取证 | 参数区回填 |

## 待废弃清单（仅标记不删除）
- 无满足三条件者
## 敏感文件清单（仅路径）
.env.example（无 .env）
## 现有 agent 设施清单（D4）
AGENTS.md(保留+加路由指针) / .opencode(工具态,保留) / 无 CLAUDE.md/.cursorrules 复本✅
## 前置缺口登记（A14）
- 无
## 工作区脏点（D2 类推处置记录）
- M scripts/coverage_matrix.py（疑似 Owner 在制品：不 stash/不 checkout/不提交；P3 commit 一律显式 git add 指定文件；汇入追认）
- ?? .github/workflows/pinned-guard.yml（子仓 main 未获提交授权→保持 untracked，遗留项）
## 回填参数区
BUILD_CMD=pip install -e .(pyproject); TEST_CMD=make test; LINT_CMD=make lint; E2E_CMD=(模块级,由根仓 e2e 统筹); E2E_RUNNER=根仓 e2e-tests.yml; REPO=Omni_Pre_Processor
