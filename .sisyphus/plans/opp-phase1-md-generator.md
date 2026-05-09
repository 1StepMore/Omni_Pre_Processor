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

- [x] 1. **创建 test_md_generator.py (RED阶段)**

  **What to do**:
  - 创建 `tests/test_md_generator.py`
  - 使用 TDD 方法：先写失败的测试
  - 测试内容：
    - `test_generate_headings_h1_h6()` - H1-H6 标题生成
    - `test_generate_headings_numbered()` - 带编号标题
    - `test_generate_headings_custom_style_mapping()` - 自定义样式映射
    - `test_generate_headings_single_level()` - 单级标题
    - `test_generate_headings_empty_level()` - 跳过空标题
    - `test_generate_headings_deep_level()` - 层级深度 > 6 时降级
    - `test_generate_lists_ordered()` - 有序列表
    - `test_generate_lists_unordered()` - 无序列表
    - `test_generate_lists_nested()` - 嵌套列表（混合）
    - `test_generate_lists_single_item()` - 单项列表
    - `test_generate_lists_empty_items()` - 空列表项
    - `test_generate_lists_deep_nesting()` - 嵌套 > 10 层时降级
    - `test_generate_tables_md_standard()` - 标准 Markdown 表格
    - `test_generate_tables_md_alignment()` - 对齐方式指定
    - `test_generate_tables_md_header_detection()` - 表头识别
    - `test_generate_tables_md_single_cell()` - 1x1 表格
    - `test_generate_tables_md_wide()` - 超宽表格（>10列）
  - 测试应该导入 MarkdownGenerator（尚未实现，会失败）
  - 测试数据使用 conftest.py 中的 fixtures 或内联简单数据

  **Must NOT do**:
  - 不要实现任何实际功能代码
  - 不要导入尚未创建的模块

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 文件创建和测试编写，模式明确，无需深度研究

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5, Task 6, Task 10 (依赖测试存在)
  - **Blocked By**: None (Wave 1 可以立即开始)

  **References**:

  **Pattern References** (existing code to follow):
  - `tests/test_docx_extractor.py:9-16` - 测试类结构 (TestDOCXExtractor)
  - `tests/test_docx_extractor.py:10-15` - 使用 fixture 的测试方法模式
  - `tests/conftest.py:19-87` - sample_files_normal fixture 结构

  **API/Type References** (contracts to implement against):
  - `src/opp/utils/dataclasses.py:21-26` - ParagraphData(text, style, level)
  - `src/opp/utils/dataclasses.py:14-18` - TableData(headers, rows)
  - `src/opp/utils/dataclasses.py:53-59` - ExtractionResult(paragraphs, tables, images)

  **WHY Each Reference Matters**:
  - `test_docx_extractor.py` 展示了测试文件的标准结构和命名
  - `ParagraphData` 等类型定义了生成器需要处理的数据结构

  **Acceptance Criteria**:

  **If TDD (tests enabled)**:
  - [ ] `tests/test_md_generator.py` 文件已创建
  - [ ] `pytest tests/test_md_generator.py -v` → **RED** (测试失败，因为 MarkdownGenerator 尚不存在)
  - [ ] 测试文件包含所有 `test_generate_*` 测试函数

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Test file creation verification
    Tool: Bash
    Preconditions: None
    Steps:
      1. ls tests/test_md_generator.py
    Expected Result: 文件存在
    Failure Indicators: 文件不存在
    Evidence: .sisyphus/evidence/task-1-file-exists.txt

  Scenario: Initial test run (should fail - RED phase)
    Tool: Bash
    Preconditions: test_md_generator.py 已创建
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -m pytest tests/test_md_generator.py -v 2>&1 | head -50
    Expected Result: 测试失败，错误信息包含 "ImportError" 或 "ModuleNotFoundError" (MarkdownGenerator 不存在)
    Failure Indicators: 测试通过（说明实现了不存在的代码）
    Evidence: .sisyphus/evidence/task-1-red-phase.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-1-file-exists.txt
  - [ ] .sisyphus/evidence/task-1-red-phase.txt

  **Commit**: NO

---

- [x] 2. **创建 test_format_protector.py (RED阶段)**

  **What to do**:
  - 创建 `tests/test_format_protector.py`
  - 使用 TDD 方法：先写失败的测试
  - 测试内容：
    - `test_detect_code_blocks_indented()` - 缩进式代码检测
    - `test_detect_code_blocks_fenced()` - 围栏代码标记 ``` 检测
    - `test_detect_code_blocks_language_detection()` - 编程语言识别
    - `test_detect_code_blocks_single_line()` - 单行代码
    - `test_detect_code_blocks_empty_block()` - 空代码块
    - `test_detect_code_blocks_nested_fences()` - 代码块中含 ```
    - `test_detect_code_blocks_pseudo_code()` - 伪代码（文本像代码）
    - `test_protect_special_chars_markdown()` - Markdown 特殊字符转义
    - `test_protect_special_chars_html_entities()` - HTML 实体处理
    - `test_protect_special_chars_latex()` - LaTeX 公式保护
    - `test_protect_special_chars_all_special()` - 全特殊字符文档
    - `test_protect_special_chars_zero_width()` - 零宽字符
    - `test_protect_special_chars_escape_cycle()` - 转义循环检测
    - `test_protect_special_chars_double_escape()` - 双重转义检测

  **Must NOT do**:
  - 不要实现任何实际功能代码
  - 不要导入尚未创建的模块

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 8, Task 9
  - **Blocked By**: None

  **References**:
  - 使用 Task 1 相同的模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `tests/test_format_protector.py` 文件已创建
  - [ ] `pytest tests/test_format_protector.py -v` → **RED** (测试失败)
  - [ ] 测试文件包含所有 `test_detect_*` 和 `test_protect_*` 测试函数

  **QA Scenarios**:

  ```
  Scenario: Test file creation verification
    Tool: Bash
    Preconditions: None
    Steps:
      1. ls tests/test_format_protector.py
    Expected Result: 文件存在
    Evidence: .sisyphus/evidence/task-2-file-exists.txt

  Scenario: Initial test run (should fail - RED phase)
    Tool: Bash
    Preconditions: test_format_protector.py 已创建
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -m pytest tests/test_format_protector.py -v 2>&1 | head -50
    Expected Result: 测试失败 (FormatProtector 不存在)
    Evidence: .sisyphus/evidence/task-2-red-phase.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-2-file-exists.txt
  - [ ] .sisyphus/evidence/task-2-red-phase.txt

  **Commit**: NO

---

- [x] 3. **创建 src/opp/markdown.py 骨架**

  **What to do**:
  - 创建 `src/opp/markdown.py`
  - 定义骨架类（方法签名，raise NotImplementedError）
  - 包含以下方法和导入：
    ```python
    from pathlib import Path
    from typing import List
    from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData, ImageData
    
    class MarkdownGenerator:
        def generate(self, result: ExtractionResult) -> str:
            raise NotImplementedError("TDD - RED phase")
        
        def generate_to_file(self, result: ExtractionResult, output_path: Path) -> None:
            raise NotImplementedError("TDD - RED phase")
        
        def generate_headings(self, paragraphs: List[ParagraphData]) -> str:
            raise NotImplementedError("TDD - RED phase")
        
        def generate_lists(self, paragraphs: List[ParagraphData]) -> str:
            raise NotImplementedError("TDD - RED phase")
        
        def generate_tables_md(self, tables: List[TableData]) -> str:
            raise NotImplementedError("TDD - RED phase")
    ```

  **Must NOT do**:
  - 不要实现任何逻辑（保持 RED 状态）
  - 不要忘记导入 Path, List, 数据类

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5, Task 6, Task 7, Task 10
  - **Blocked By**: Task 1 (test file must exist first for import validation)

  **References**:

  **Pattern References**:
  - `src/opp/extractors/base.py:16-49` - ExtractorBase 类结构
  - `src/opp/extractors/docx.py:20-49` - extract() 方法签名模式

  **WHY Each Reference Matters**:
  - ExtractorBase 展示了 OPP 项目的类结构模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `src/opp/markdown.py` 文件已创建
  - [ ] `from opp.markdown import MarkdownGenerator` 可执行

  **QA Scenarios**:

  ```
  Scenario: Module import verification
    Tool: Bash
    Preconditions: markdown.py 已创建
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "from opp.markdown import MarkdownGenerator; print('Import OK')"
    Expected Result: 输出 "Import OK"，无错误
    Evidence: .sisyphus/evidence/task-3-import.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-3-import.txt

  **Commit**: NO

---

- [x] 4. **创建 src/opp/format_protector.py 骨架**

  **What to do**:
  - 创建 `src/opp/format_protector.py`
  - 定义骨架类：
    ```python
    class FormatProtector:
        def detect_code_blocks(self, text: str) -> List[dict]:
            raise NotImplementedError("TDD - RED phase")
        
        def protect_special_chars(self, text: str) -> str:
            raise NotImplementedError("TDD - RED phase")
    ```

  **Must NOT do**:
  - 不要实现任何逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 8, Task 9
  - **Blocked By**: Task 2

  **References**:
  - 使用 Task 3 相同的模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `src/opp/format_protector.py` 文件已创建
  - [ ] `from opp.format_protector import FormatProtector` 可执行

  **QA Scenarios**:

  ```
  Scenario: Module import verification
    Tool: Bash
    Preconditions: format_protector.py 已创建
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "from opp.format_protector import FormatProtector; print('Import OK')"
    Expected Result: 输出 "Import OK"
    Evidence: .sisyphus/evidence/task-4-import.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-4-import.txt

  **Commit**: NO

---

- [x] 5. **实现 generate_headings() 方法**

  **What to do**:
  - 实现 `src/opp/markdown.py` 中的 `generate_headings()` 方法
  - 功能：接收 ParagraphData 列表，返回 markdown 标题字符串
  - 规则：
    - H1-H6 使用 `#` 到 `######`
    - `level=None` 或 `level<1` 的段落跳过
    - `level>6` 降级为 H6（加警告）
    - 标题文本应该被 `protect_special_chars()` 处理
  - 运行 Task 1 的测试，确保全部通过

  **Must NOT do**:
  - 不要实现其他方法（只实现 generate_headings）
  - 不要忘记处理 level > 6 的情况

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要理解 ParagraphData 结构并正确映射到 MD 格式

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `src/opp/utils/dataclasses.py:21-26` - ParagraphData 结构

  **WHY Each Reference Matters**:
  - ParagraphData 决定如何读取 text, style, level

  **Acceptance Criteria**:

  **If TDD (tests enabled)**:
  - [ ] `pytest tests/test_md_generator.py -v -k "headings"` → 全部通过

  **QA Scenarios**:

  ```
  Scenario: H1-H6 heading generation
    Tool: Bash
    Preconditions: generate_headings() 已实现
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ParagraphData
mg = MarkdownGenerator()
paras = [ParagraphData(text='Title', style='Heading 1', level=1)]
print(mg.generate_headings(paras))
"
    Expected Result: 输出 "# Title"
    Evidence: .sisyphus/evidence/task-5-h1.txt

  Scenario: Level 7降级处理
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ParagraphData
mg = MarkdownGenerator()
paras = [ParagraphData(text='Deep', style='Heading 7', level=7)]
result = mg.generate_headings(paras)
print('######' in result)  # 应该是 H6
"
    Expected Result: True (level 7 降级为 H6)
    Evidence: .sisyphus/evidence/task-5-level7.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-5-h1.txt
  - [ ] .sisyphus/evidence/task-5-level7.txt

  **Commit**: YES
  - Message: `feat(md): implement generate_headings() method`
  - Files: `src/opp/markdown.py`

---

- [x] 6. **实现 generate_lists() 方法**

  **What to do**:
  - 实现 `generate_lists()` 方法
  - 功能：接收 ParagraphData 列表，返回 markdown 列表字符串
  - 规则：
    - 识别 `style` 包含 "List" 或 "Number" 的段落
    - 有序列表使用 `1. ` 格式
    - 无序列表使用 `- ` 格式
    - 嵌套列表通过缩进表示（最大 6 层）
    - 嵌套 > 10 层时降级为平面列表

  **Must NOT do**:
  - 不要实现其他方法

  **Recommended Agent Profile**:
  - **Category**: `deep`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Task 3

  **References**:
  - 使用 Task 5 相同的模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `pytest tests/test_md_generator.py -v -k "lists"` → 全部通过

  **QA Scenarios**:

  ```
  Scenario: Unordered list generation
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ParagraphData
mg = MarkdownGenerator()
paras = [ParagraphData(text='Item', style='List Bullet', level=None)]
print(mg.generate_lists(paras))
"
    Expected Result: 输出 "- Item"
    Evidence: .sisyphus/evidence/task-6-unordered.txt

  Scenario: Deep nesting limit
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ParagraphData
# 测试嵌套层级限制
mg = MarkdownGenerator()
paras = [ParagraphData(text='Deep item', style='List', level=None)]
result = mg.generate_lists(paras)
"
    Expected Result: 列表被正确生成
    Evidence: .sisyphus/evidence/task-6-nesting.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-6-unordered.txt
  - [ ] .sisyphus/evidence/task-6-nesting.txt

  **Commit**: YES
  - Message: `feat(md): implement generate_lists() method`
  - Files: `src/opp/markdown.py`

---

- [x] 7. **实现 generate_tables_md() 方法**

  **What to do**:
  - 实现 `generate_tables_md()` 方法
  - 功能：接收 TableData 列表，返回 markdown 表格字符串
  - 规则：
    - 简单字符串格式化（无 pandas/tabulate）
    - 表头行 + 分隔行 `|---|---|` + 数据行
    - 单元格中的 `|` 转义为 `\\|`
    - 单元格中的换行替换为空格
    - `>10` 列时添加横向滚动警告注释
    - 1x1 表格正常处理

  **Must NOT do**:
  - 不要使用 pandas/tabulate
  - 不要实现其他方法

  **Recommended Agent Profile**:
  - **Category**: `deep`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Task 3, Task 4

  **References**:

  **Pattern References**:
  - `src/opp/utils/dataclasses.py:14-18` - TableData 结构

  **WHY Each Reference Matters**:
  - TableData 定义了 headers (list[str]) 和 rows (list[list[str]])

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `pytest tests/test_md_generator.py -v -k "tables"` → 全部通过

  **QA Scenarios**:

  ```
  Scenario: Standard table generation
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import TableData
mg = MarkdownGenerator()
tables = [TableData(headers=['A', 'B'], rows=[['1', '2']])]
print(mg.generate_tables_md(tables))
"
    Expected Result: 正确格式的 markdown 表格
    Evidence: .sisyphus/evidence/task-7-standard.txt

  Scenario: Pipe character escaping
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import TableData
mg = MarkdownGenerator()
tables = [TableData(headers=['A|B'], rows=[['C|D']])]
result = mg.generate_tables_md(tables)
print('\\\\|' in result or '|' not in result.split('\\n')[0])
"
    Expected Result: True (pipe 被转义)
    Evidence: .sisyphus/evidence/task-7-pipe.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-7-standard.txt
  - [ ] .sisyphus/evidence/task-7-pipe.txt

  **Commit**: YES
  - Message: `feat(md): implement generate_tables_md() method`
  - Files: `src/opp/markdown.py`

---

- [x] 8. **实现 detect_code_blocks() 方法**

  **What to do**:
  - 实现 `src/opp/format_protector.py` 中的 `detect_code_blocks()` 方法
  - 功能：检测文本中的代码块（缩进式和围栏式）
  - 规则：
    - 缩进式代码：检测 4 空格或 Tab 缩进的行
    - 围栏式代码：检测 ``` 或 ~~~ 标记
    - 语言识别：从 ``` 后的语言标识符提取
    - 单行代码：行内 `` ` `` 包裹的内容
    - 伪代码检测：排除像代码但不是代码的文本

  **Must NOT do**:
  - 不要实现 protect_special_chars()

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 9)
  - **Blocks**: Task 12
  - **Blocked By**: Task 4

  **References**:
  - 使用 Task 5 的模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `pytest tests/test_format_protector.py -v -k "detect"` → 全部通过

  **QA Scenarios**:

  ```
  Scenario: Fenced code block detection
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.format_protector import FormatProtector
fp = FormatProtector()
text = '```python\\nprint(\"hello\")\\n```'
result = fp.detect_code_blocks(text)
print(len(result) > 0)
"
    Expected Result: True (检测到代码块)
    Evidence: .sisyphus/evidence/task-8-fenced.txt

  Scenario: Language detection
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.format_protector import FormatProtector
fp = FormatProtector()
text = '```javascript\\nvar x = 1;\\n```'
result = fp.detect_code_blocks(text)
print(result[0].get('language') if result else 'None')
"
    Expected Result: "javascript"
    Evidence: .sisyphus/evidence/task-8-lang.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-8-fenced.txt
  - [ ] .sisyphus/evidence/task-8-lang.txt

  **Commit**: YES
  - Message: `feat(protect): implement detect_code_blocks() method`
  - Files: `src/opp/format_protector.py`

---

- [x] 9. **实现 protect_special_chars() 方法**

  **What to do**:
  - 实现 `protect_special_chars()` 方法
  - 功能：转义 Markdown 特殊字符
  - 规则：
    - Markdown 特殊字符：`\ * _ [ ] ( ) # + - . ! |`
    - HTML 实体：`&lt;` `&gt;` `&amp;` 等
    - LaTeX 公式保护：保留 `$...$` 和 `$$...$$`
    - 零宽字符：移除或保留
    - 不在代码块内的字符才被转义

  **Must NOT do**:
  - 不要转义代码块内的字符
  - 不要实现其他方法

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8)
  - **Blocks**: Task 12
  - **Blocked By**: Task 4

  **References**:
  - 使用 Task 8 的模式

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] `pytest tests/test_format_protector.py -v -k "protect"` → 全部通过

  **QA Scenarios**:

  ```
  Scenario: Markdown special chars protection
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.format_protector import FormatProtector
fp = FormatProtector()
result = fp.protect_special_chars('*bold* and _italic_')
print('\\*' in result and '\\_' in result)
"
    Expected Result: True
    Evidence: .sisyphus/evidence/task-9-md-chars.txt

  Scenario: Code block content not escaped
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.format_protector import FormatProtector
fp = FormatProtector()
text = '```\\n*not bold*\\n```'
result = fp.protect_special_chars(text)
print('\\*' not in result.split('```')[1])  # 代码块内不应被转义
"
    Expected Result: True
    Evidence: .sisyphus/evidence/task-9-code-block.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-9-md-chars.txt
  - [ ] .sisyphus/evidence/task-9-code-block.txt

  **Commit**: YES
  - Message: `feat(protect): implement protect_special_chars() method`
  - Files: `src/opp/format_protector.py`

---

- [x] 10. **MarkdownGenerator 集成**

  **What to do**:
  - 实现 `generate()` 方法，调用 generate_headings(), generate_lists(), generate_tables_md()
  - 实现 `generate_to_file()` 方法，写入文件并保存图片
  - 将 FormatProtector 集成到生成流程
  - 图片文件命名：`{output_stem}_image_{n}.png`
  - 所有组件联合测试

  **Must NOT do**:
  - 不要实现图片去重（guardrail）
  - 不要添加链接保留

  **Recommended Agent Profile**:
  - **Category**: `deep`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: None (Wave 3, sequential)
  - **Blocks**: Task 11, Task 12, F1
  - **Blocked By**: Task 5, Task 6, Task 7

  **References**:

  **Pattern References**:
  - `src/opp/extractors/docx.py:76-96` - extract_images 模式（ImageData 写入）

  **WHY Each Reference Matters**:
  - DOCXExtractor.shows how to write ImageData to files

  **Acceptance Criteria**:

  **If TDD**:
  - [ ] 所有 test_md_generator.py 测试通过

  **QA Scenarios**:

  ```
  Scenario: Full generation flow
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ExtractionResult, ParagraphData, TableData
mg = MarkdownGenerator()
result = ExtractionResult(
    paragraphs=[ParagraphData(text='Title', style='Heading 1', level=1)],
    tables=[TableData(headers=['A'], rows=[['B']])],
    images=[]
)
md = mg.generate(result)
print(len(md) > 0 and '# Title' in md)
"
    Expected Result: True
    Evidence: .sisyphus/evidence/task-10-full.txt

  Scenario: Image file output
    Tool: Bash
    Steps:
      1. cd /tmp && python -c "
from pathlib import Path
from opp.markdown import MarkdownGenerator
from opp.utils.dataclasses import ImageData
import hashlib
mg = MarkdownGenerator()
img = ImageData(name='test.png', data=b'fake', md5='abc', mime_type='image/png')
mg._write_image(img, Path('/tmp/test.png'))
print(Path('/tmp/test.png').exists())
"
    Expected Result: True
    Evidence: .sisyphus/evidence/task-10-image.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-10-full.txt
  - [ ] .sisyphus/evidence/task-10-image.txt

  **Commit**: YES
  - Message: `feat(integration): implement MarkdownGenerator.generate() and image output`
  - Files: `src/opp/markdown.py`

---

- [x] 11. **更新 src/opp/__init__.py 导出**

  **What to do**:
  - 更新 `src/opp/__init__.py`
  - 添加 MarkdownGenerator 到导出列表
  - 确保 `from opp import MarkdownGenerator` 可用

  **Must NOT do**:
  - 不要添加其他导出（保持简单）

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: Task 10

  **References**:

  **Pattern References**:
  - `src/opp/__init__.py:9-15` - 当前导出模式

  **Acceptance Criteria**:

  - [ ] `from opp import MarkdownGenerator` 可执行

  **QA Scenarios**:

  ```
  Scenario: Public import verification
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -c "from opp import MarkdownGenerator; print('OK')"
    Expected Result: 输出 "OK"
    Evidence: .sisyphus/evidence/task-11-import.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-11-import.txt

  **Commit**: YES
  - Message: `feat(api): export MarkdownGenerator from opp package`
  - Files: `src/opp/__init__.py`

---

- [x] 12. **重构消除重复代码**

  **What to do**:
  - 检查 markdown.py 和 format_protector.py 中的重复代码
  - 提取公共函数到共享位置（如 utils/）
  - 确保测试仍然全部通过

  **Must NOT do**:
  - 不要添加新功能
  - 不要改变公开 API

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: Task 8, Task 9, Task 10

  **References**:
  - 使用重构最佳实践

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_md_generator.py tests/test_format_protector.py -v` → 全部通过
  - [ ] 代码行数减少或不变（不增加）

  **QA Scenarios**:

  ```
  Scenario: All tests still pass after refactor
    Tool: Bash
    Steps:
      1. cd /mnt/d/贯维/Omni_Pre_Processor && python -m pytest tests/test_md_generator.py tests/test_format_protector.py -v
    Expected Result: 全部通过
    Evidence: .sisyphus/evidence/task-12-refactor.txt
  ```

  **Evidence to Capture:**
  - [ ] .sisyphus/evidence/task-12-refactor.txt

  **Commit**: YES
  - Message: `refactor(md): extract common utilities`
  - Files: 待定（根据重构结果）

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search for forbidden patterns. Check evidence files exist.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check .` + `pytest`. Review for: empty catches, console.log, unused imports, AI slop patterns.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario. Test edge cases. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify diff. Check "Must NOT do" compliance. Flag cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N] | VERDICT`

---

## Commit Strategy

- Wave 1 (T1-T4): NO commits (skeleton only)
- Wave 2:
  - T5: `feat(md): implement generate_headings() method` - markdown.py
  - T6: `feat(md): implement generate_lists() method` - markdown.py
  - T7: `feat(md): implement generate_tables_md() method` - markdown.py
  - T8: `feat(protect): implement detect_code_blocks() method` - format_protector.py
  - T9: `feat(protect): implement protect_special_chars() method` - format_protector.py
- Wave 3:
  - T10: `feat(integration): implement MarkdownGenerator.generate() and image output` - markdown.py
  - T11: `feat(api): export MarkdownGenerator from opp package` - __init__.py
  - T12: `refactor(md): extract common utilities` - markdown.py, format_protector.py

---

## Success Criteria

### Verification Commands
```bash
pytest tests/test_md_generator.py -v  # Expected: all pass
pytest tests/test_format_protector.py -v  # Expected: all pass
```

### Final Checklist
- [x] 所有 Must Have 存在
- [x] 所有 Must NOT Have 不存在
- [x] 所有测试通过