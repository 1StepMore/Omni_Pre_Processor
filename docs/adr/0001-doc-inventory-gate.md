# 0001. 文档真值门禁（doc_inventory + ADR 体系）

- 状态：已接受
- 日期：2026-10-31
- 决策人：maintainer（issue OPP#111）

## 背景

OPP 的 README / AGENTS 携带会随功能变化的数字（输入格式数、MCP 工具数），
此前没有任何机制校验它们与源码派生值一致——文档必然腐烂，agent 与用户
读到过期信息；架构决策也没有 ADR 可追溯。

## 决策

1. 新增 `scripts/doc_inventory.py`：
   - **派生**活体数字——MCP 工具（`opp.mcp.server._TOOL_SCHEMAS`）、输入
     格式（`get_capabilities._INPUT_FORMATS`）、extractor 类数、场景数与
     tier 拆分（scenarios 递归 glob + 行级 tier 正则）、pyproject 版本；
   - **门禁**声明点（README/AGENTS 中的 `N input formats`、
     `MCP tools (N total)` 等）与派生值比对；`--check` exit 1 = 有漂移；
   - 生成 `docs/dev/doc-inventory.md` 行集（生成物必须新鲜，不一致即
     fail）；README/AGENTS 反引号路径做存在性检查（本仓 / 父仓 /
     兄弟子仓三根解析）。
2. 新增 `docs/adr/`（本目录）：TEMPLATE + 索引，架构决策逐条记录。
3. CI（ci.yml）加 `doc_inventory --check` 步骤，文档漂移在 PR 即被拦下。

## 备选方案

- **手写一致性检查脚本（AutoMedia check-doc-consistency 模式）** —— 与
  doc_inventory 相比缺少「生成行集 + 新鲜度」这一半，声明漂移仍靠人眼；
  未选。
- **不做门禁，靠 review 纪律** —— 实测不可靠：本门禁上线前就抓到 2 个
  真实断链（`tests/test_pipeline.py`、OL 的旧 `ol_xliff/repair` 路径），
  都是 review 放过来的。

## 后果

- 正面：README/AGENTS 的关键数字从「希望是对的」变成「CI 强制为对」；
  断链引用在 PR 阶段暴露。
- 负面 / 代价：改 README/AGENTS 后必须重新生成 inventory（一条命令）；
  声明点清单需要随新文档维护。
- 中性：`scripts/` 成为可导入包（`scripts/doc_inventory.py` 自举 suite
  根以便包导入与直执行两用）。

## 验证

- `python scripts/doc_inventory.py --check` exit 0；
- 故意改错 README 的 "16 input formats" → --check exit 1（本 PR 开发期
  实测，见 PR 描述）。
