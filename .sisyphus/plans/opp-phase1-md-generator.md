# OPP Phase 1: MD通道输出 - 工作计划

## TL;DR

> **快速摘要**: 为 OPP 实现 Markdown 结构化生成器，支持标题/列表/表格生成、代码块检测、特殊字符保护
>
> **交付物**:
> - `src/opp/markdown.py` - MarkdownGenerator 主模块
> - `src/opp/format_protector.py` - 格式保护器（代码块检测、特殊字符转义）
> - `tests/test_md_generator.py` - MD生成器单元测试
> - `tests/test_format_protector.py` - 格式保护器单元测试
>
> **预估工期**: 1.5 天
> **并行执行**: YES - 3 waves
> **关键路径**: test_md_generator.py → markdown.py → test_format_protector.py → format_protector.py → integration

---

## Context

### 原始需求
Phase 1 实现 MD通道输出（来自 OPP_DD_Vibe_Phase版.md）：
- 实现Markdown结构化生成器（标题/列表/表格）
- 实现代码块与特殊字符保护
- 实现图片资源统一管理与路径维护

### 访谈总结

**关键讨论**:
- Phase 0 已完成三个格式提取器 (DOCX/PPTX/PDF)
- ExtractionResult 数据结构: paragraphs (List[ParagraphData]), tables (List[TableData]), images (List[ImageData])
- 数据类定义: ParagraphData(text, style, level), TableData(headers, rows), ImageData(name, data, md5, mime_type)
- 测试策略: **TDD** (先写测试，再实现)
- 图片命名: **扁平结构** (output_image_1.png 放在 MD 同目录)
- 依赖: **无 pandas/tabulate**，使用简单字符串格式化

**测试优先方法**:
```
1. 先写测试 (test_md_generator.py, test_format_protector.py)
2. 运行测试 → 全部失败 (RED)
3. 实现代码直到测试通过 (GREEN)
4. 重构优化 (REFACTOR)
```

### Metis 审查

**识别的缺口** (已处理):
- ImageData.data 格式: 假设为可直接写入的 bytes（从现有代码确认）
- 表格 cell 含 `|` 字符: 将转义为 `\\|`
- 空输入: 返回空字符串
- 深层嵌套列表: 限制最大 6 层

---

## Work Objectives

### 核心目标
将 ExtractionResult (paragraphs, tables, images) 转换为格式正确的 Markdown 文本

### 具体交付物
- `src/opp/markdown.py` - MarkdownGenerator 类
- `src/opp/format_protector.py` - FormatProtector 类
- `src/opp/__init__.py` - 更新导出 MarkdownGenerator
- `tests/test_md_generator.py` - 生成器测试
- `tests/test_format_protector.py` - 格式保护器测试

### 完成定义
- [ ] `pytest tests/test_md_generator.py` → 全部通过
- [ ] `pytest tests/test_format_protector.py` → 全部通过
- [ ] 图片文件正确输出到同目录 (output_image_N.png)
- [ ] Markdown 输出为 UTF-8 编码

### Must Have
- 标题层级 H1-H6 正确生成
- 有序/无序列表结构正确
- 表格使用标准 Markdown 格式
- 特殊字符正确转义
- 代码块内容不被误转义

### Must NOT Have (Guardrails)
- ❌ 图片去重逻辑
- ❌ 链接/URL 保留
- ❌ 目录生成 (TOC)
- ❌ 批处理或多文件输出
- ❌ 可配置的 Markdown 变体

---

## Verification Strategy

### Test Decision
- **测试基础设施存在**: YES (pytest + pytest-cov)
- **自动化测试**: TDD (先写测试后实现)
- **框架**: pytest
- **工作流**: RED (失败测试) → GREEN (实现通过) → REFACTOR (优化)

### QA Policy
每个任务必须包含 agent-executed QA scenarios。

**验证命令**:
```bash
pytest tests/test_md_generator.py -v  # 期望: 全部通过
pytest tests/test_format_protector.py -v  # 期望: 全部通过
ls output_image_*.png  # 期望: 文件存在
file output.md  # 期望: UTF-8 编码
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (立即开始 - 基础建设):
├── Task 1: 创建 test_md_generator.py (RED阶段)
├── Task 2: 创建 test_format_protector.py (RED阶段)
├── Task 3: 创建 src/opp/markdown.py 骨架
└── Task 4: 创建 src/opp/format_protector.py 骨架

Wave 2 (Wave 1 完成后 - 核心实现, 最大并行):
├── Task 5: 实现 generate_headings() [deep]
├── Task 6: 实现 generate_lists() [deep]
├── Task 7: 实现 generate_tables_md() [deep]
├── Task 8: 实现 detect_code_blocks() [quick]
└── Task 9: 实现 protect_special_chars() [quick]

Wave 3 (Wave 2 完成后 - 集成与重构):
├── Task 10: MarkdownGenerator 集成 (联合测试)
├── Task 11: 更新 src/opp/__init__.py 导出
└── Task 12: 重构消除重复代码

Wave FINAL (所有任务完成后 - 4个并行审查):
├── Task F1: Plan Compliance Audit (oracle)
├── Task F2: Code Quality Review (unspecified-high)
├── Task F3: Real Manual QA (unspecified-high)
└── Task F4: Scope Fidelity Check (deep)
-> 展示结果 -> 获取用户明确同意

关键路径: T1 → T5 → T6 → T10 → F1-F4 → user ok
并行加速: ~60% vs 顺序执行
最大并发: 4 (Wave 1), 5 (Wave 2)
```

### Dependency Matrix

- **T1**: - - T5, T6, T10, T2
- **T2**: - - T8, T9, T12, T3
- **T3**: T1 - T5, T6, T10, T4
- **T4**: T2 - T8, T9, T12, T3
- **T5**: T3 - T10, T4
- **T6**: T3 - T10, T4
- **T7**: T3, T4 - T10, T11
- **T8**: T4 - T12, T5
- **T9**: T4 - T12, T6
- **T10**: T5, T6, T7 - T11, T12, F1
- **T11**: T7 - F1, F2, F3, F4
- **T12**: T8, T9 - F1, F2, F3, F4

> 详细依赖见各任务说明

---

## TODOs

---

## Final Verification Wave

---

## Commit Strategy

---

## Success Criteria

### Verification Commands
```bash
pytest tests/test_md_generator.py -v  # Expected: all pass
pytest tests/test_format_protector.py -v  # Expected: all pass
```

### Final Checklist
- [ ] 所有 Must Have 存在
- [ ] 所有 Must NOT Have 不存在
- [ ] 所有测试通过