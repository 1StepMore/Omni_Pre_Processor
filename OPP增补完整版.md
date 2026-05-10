# Omni-Pre-Processor (OPP) 开发计划 – DD Vibe Phase 完整版

## 文档信息

- **版本**: v4.0-Phase-Full

- **执行方式**: 按Phase逐个喂给vibe智能体执行

- **核心功能**: DOCX/PPTX/PDF/XLSX/CSV/JSON/XML/HTML/EPUB/EML/MSG/Image → MD结构化清洗 + XLIFF标准化导出

- **开发哲学**: 纯 Vibe Coding，不造轮子，只写粘合剂代码，将成熟轮子接入OPP统一管线

- **生效日期**: 2026年5月

---

## Phase 0: 环境搭建与核心提取器构建

### 📋 Phase 0 执行计划

#### 1. 概述与目标

- 搭建项目仓库结构，配置CI/CD

- 实现DOCX/PPTX/PDF三格式核心内容提取器

- 构建统一的内容提取抽象层

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| DOCX 解析 | python-docx | Word文档结构解析 |
| PPTX 解析 | python-pptx | PowerPoint解析 |
| PDF 解析 | PyMuPDF (fitz) | PDF文本与布局提取 |
| 测试框架 | pytest | 单元测试与集成测试 |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_docx_extractor.py`, `tests/test_pptx_extractor.py`, `tests/test_pdf_extractor.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **DOCX核心提取器** | | | |
| `extract_paragraphs()` | 标准标题层级<br>带样式段落<br>多级列表 | 空文档<br>单段落文档<br>1000页超大文档 | 损坏的DOCX<br>密码保护文档<br>不兼容版本 |
| `extract_tables()` | 简单行列表格<br>带表头表格<br>带合并单元格 | 单行表格<br>单列表格<br>嵌套表格三层 | 表格跨页断裂<br>隐形表格<br>0行0列表格 |
| `extract_images()` | JPG嵌入图片<br>PNG嵌入图片<br>多图文档 | 单图文档<br>超大分辨率图<br>重复图片 | 不支持格式<br>损坏图片<br>0字节图片 |
| **PPTX核心提取器** | | | |
| `extract_slides()` | 标准演示文稿<br>带备注幻灯片<br>带布局模板 | 单幻灯片文档<br>空白幻灯片<br>1000页超大PPT | 损坏的PPTX<br>宏启用文档<br>不兼容版本 |
| `extract_shapes()` | 文本框提取<br>形状文本提取<br>SmartArt提取 | 无形状幻灯片<br>重叠形状<br>群组形状 | 自定义形状<br>3D对象<br>嵌入OLE对象 |
| `extract_notes()` | 演讲者备注<br>每页独立备注<br>带格式备注 | 空备注<br>超长备注<br>备注中含表格 | 备注母版异常<br>隐藏备注 |
| **PDF核心提取器** | | | |
| `extract_text_blocks()` | 原生PDF文本<br>带排版布局<br>多栏布局 | 纯图片PDF<br>单页PDF<br>加密PDF（可解密） | 扫描件PDF（OCR失败）<br>损坏PDF<br>0字节PDF |
| `detect_tables()` | 标准有线表格<br>无线表格<br>跨页表格 | 无表格文档<br>单格表格<br>极度复杂表格 | 伪表格（文本对齐）<br>图片表格 |
| `extract_images_pdf()` | PDF嵌入图片<br>扫描页图片<br>高分辨率图 | 无图PDF<br>压缩率99%图片 | CCITT格式无法解码<br>损坏图片流 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. DOCX提取：标题层级识别准确率≥95%（100个标准样本）

2. PPTX提取：文本框+形状+备注完整提取率100%

3. PDF提取：原生PDF文本提取准确率≥98%

4. 三格式图片提取：所有嵌入图片都能导出到指定目录

5. CI/CD流水线新增格式兼容性测试门禁

#### ❌ 异常流程验收标准

1. 损坏文件检测：自动识别并报告损坏文档，不崩溃

2. 密码保护文档：清晰提示"需要密码"并优雅退出

3. 纯图片PDF：自动降级并提示"建议OCR处理"

4. 内存超限：自动触发分页处理，不OOM崩溃

#### 🔲 边界条件验收标准

1. 单个文档页数上限：10,000页（超出触发警告和分页处理）

2. 单个文件大小上限：500MB（超出自动降级流式处理）

3. 表格复杂度上限：嵌套≤3层，行列数≤100（超出降级为原始文本）

4. Python版本要求≥3.8（类型提示依赖）

#### ⚡ 非功能性验收标准

1. 提取性能≥20MB/s（单线程）

2. 内存开销≤原始文件大小的2倍

3. 图片导出准确率100%（MD5校验匹配）

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：DOCX文档基础提取**

Given：用户有一个标准DOCX文档 sample.docx

When：用户执行 opp extract sample.docx --format json

Then：

• 输出JSON包含所有段落文本

• 标题层级H1-H6正确识别

• 所有表格内容提取为结构化数据

• 所有图片导出到images/目录

**场景2：PPTX演示文稿提取**

Given：用户有一个PPTX演示文稿 demo.pptx

When：用户执行 opp extract demo.pptx --include-notes

Then：

• 每页幻灯片文本按顺序提取

• 演讲者备注包含在每页末尾

• 形状和SmartArt文本全部提取

**场景3：PDF文档智能提取**

Given：用户有一个原生PDF文档 doc.pdf

When：用户执行 opp extract doc.pdf

Then：

• 文本按阅读顺序重组

• 多栏布局自动识别合并

• 表格自动检测并结构化

---

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| **🔴 红** | 先写三个提取器的所有测试用例 | 测试全部失败（证明测试有效） |
| **🟢 绿** | 编写DOCX/PPTX/PDF提取器代码 | 所有测试通过 |
| **🔄 重构** | 抽象统一提取接口，消除三格式重复代码 | 测试仍然全部通过 |

**本Phase测试交付物清单**：

- `tests/test_docx_extractor.py`（DOCX段落/表格/图片提取）

- `tests/test_pptx_extractor.py`（PPTX幻灯片/形状/备注提取）

- `tests/test_pdf_extractor.py`（PDF文本块/表格/图片提取）

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 格式版本差异大 | 提取遗漏 | 多版本样本收集+兼容性测试矩阵 |
| PDF布局千变万化 | 结构提取不准 | 布局后验证+降级策略+人工标注修正 |

---

## Phase 1: MD通道输出

### 📋 Phase 1 执行计划

#### 1. 概述与目标

- 实现Markdown结构化生成器（标题/列表/表格）

- 实现代码块与特殊字符保护

- 实现图片资源统一管理与路径维护

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| 表格处理 | pandas + tabulate | 表格结构化转换 |
| 特殊字符处理 | 自研 | Markdown特殊字符转义保护 |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_md_generator.py`, `tests/test_format_protector.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **Markdown结构化生成器** | | | |
| `generate_headings()` | H1-H6完整层级<br>带编号标题<br>自定义样式映射 | 单级标题<br>跳过空标题<br>层级深度>6 | 样式映射冲突<br>无效层级编号 |
| `generate_lists()` | 有序列表<br>无序列表<br>嵌套列表（混合） | 单项列表<br>空列表项<br>嵌套>10层 | 列表编号断裂<br>缩进不一致 |
| `generate_tables_md()` | 标准Markdown表格<br>对齐方式指定<br>表头识别 | 1x1表格<br>超宽表格（>10列） | 单元格含换行<br>Markdown特殊字符 |
| **代码块与格式保护** | | | |
| `detect_code_blocks()` | 缩进式代码<br>围栏代码标记<br>编程语言识别 | 单行代码<br>空代码块<br>代码块中含``` | 伪代码（文本像代码）<br>嵌套标记 |
| `protect_special_chars()` | Markdown特殊字符转义<br>HTML实体处理<br>LaTeX公式保护 | 全特殊字符文档<br>零宽字符 | 转义循环<br>双重转义 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. 标准DOCX→MD转换：标题、段落、列表、表格格式无损率100%（30个标准样本）

2. 图片引用路径100%正确，无断链

3. 特殊字符转义100%正确，不破坏Markdown渲染

4. 代码块标记100%正确匹配和闭合

#### ❌ 异常流程验收标准

1. 检测到无法保留的格式自动添加警告注释

2. 表格过于复杂无法MD表示时自动回退为HTML表格

3. 嵌套过深列表自动降级为平面列表并添加警告

4. 检测到潜在渲染问题自动创建diff报告

#### 🔲 边界条件验收标准

1. 纯图片文档生成空MD+图片目录（输出警告）

2. 全角/半角混合自动规范化（可配置开关）

3. 表格列数>10时自动启用横向滚动标记

4. 文件名含特殊字符自动规范化处理

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：DOCX文档的完整转换流程**

Given：用户有一个 DOCX 格式的用户手册 manual.docx

When：用户执行 opp convert manual.docx --target-format md --output manual.md

Then：

• manual.md 生成成功

• 标题层级（H1-H6）保持不变

• 段落格式保持完整

• 有序/无序列表结构保持

• 表格转换为标准 Markdown 表格

• 所有嵌入图片提取到 images/ 目录

• 图片在 MD 中的引用路径正确

**场景2：PPTX演示文稿转换**

Given：用户有一个 PPTX 演示文稿 presentation.pptx

When：用户执行 opp convert presentation.pptx --target-format md

Then：

• 每页幻灯片生成一个二级标题（## 幻灯片 N）

• 幻灯片中的文本框按阅读顺序提取

• 演讲者备注放在每个幻灯片末尾，用 > 引用

• 图片提取到 images/slide_N_*.png

**场景3：PDF文档智能转换**

Given：用户有一个原生PDF文档 document.pdf

When：用户执行 opp convert document.pdf --target-format md --ocr-engine tesseract

Then：

• 如果是原生PDF：直接提取文本，保持排版

• 如果是扫描件PDF：自动调用OCR引擎识别

• 表格自动检测并转换为Markdown表格

• 文本按栏布局自动重组为线性阅读顺序

---

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| **🔴 红** | 先写MD生成器和格式保护的所有测试 | 测试全部失败 |
| **🟢 绿** | 编写MD生成和格式保护代码 | 所有测试通过 |
| **🔄 重构** | 优化生成逻辑，统一三格式输出 | 测试仍然全部通过 |

**本Phase测试交付物**：

- `tests/test_md_generator.py`（Markdown标题/列表/表格生成）

- `tests/test_format_protector.py`（代码块检测/特殊字符保护）

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 复杂表格转换失真 | 信息丢失 | 表格复杂度检测+超复杂表格降级处理 |
| 特殊字符破坏渲染 | MD无法预览 | 转义后渲染验证+diff报告 |

---

## Phase 2: XLIFF通道输出

### 📋 Phase 2 执行计划

#### 1. 概述与目标

- 实现XLIFF 1.2/2.0标准生成器

- 实现翻译单元分段与对齐

- 实现XLIFF标准合规验证器

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| XLIFF 导出 | translate-toolkit | XLIFF标准格式生成 |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_xliff_generator.py`, `tests/test_xliff_validator.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **XLIFF标准生成器** | | | |
| `create_trans_unit()` | 标准翻译单元<br>带资源标注<br>带上下文注释 | 空文本单元<br>单字符单元<br>10000字超长单元 | 控制字符污染<br>无效XML字符 |
| `set_file_attributes()` | source/target语言设置<br>工具版本标注<br>原始文件引用 | 未知语言代码<br>长路径引用 | 无效ISO语言码<br>XML属性转义 |
| `generate_xliff_file()` | XLIFF 1.2标准输出<br>XLIFF 2.0标准输出<br>骨架文件关联 | 单单元XLIFF<br>10000单元大文件 | 不兼容版本<br>XML命名空间错误 |
| **XLIFF验证器** | | | |
| `validate_xliff_schema()` | XSD schema验证<br>命名空间验证 | 最小合法XLIFF | 无效XML<br>不兼容版本 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. XLIFF文件100%通过OASIS标准验证

2. 翻译单元100%与原文段落对应

3. 所有上下文注释完整保留

4. XLIFF可被主流CAT工具（Trados、memoQ）正常打开

#### ❌ 异常流程验收标准

1. XML生成错误自动报告具体位置和原因

2. 控制字符自动过滤或转义

3. 无效语言代码自动降级为通用代码

4. 超大文件自动分块生成

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：XLIFF标准导出**

Given：用户有一个 DOCX 文档 manual.docx

When：用户执行 opp convert manual.docx --target-format xlf --output manual.xlf

Then：

• manual.xlf 生成成功，符合XLIFF 1.2标准

• 每个段落/标题生成一个 <trans-unit>

• source 语言正确设置为文档原始语言

• 每个单元包含原始位置信息（文件+行号）

• XLIFF文件可被主流CAT工具正常打开

**场景2：双格式同时导出**

Given：用户有一个 DOCX 文档 manual.docx

When：用户执行 opp convert manual.docx --target-format both --output-dir output/

Then：

• output/manual.md 生成成功

• output/manual.xlf 生成成功

• output/images/ 目录包含所有提取的图片

• MD和XLIFF中的文本内容一一对应

• 两种格式的段落编号可互相对照

---

### 🔄 TDD - 测试驱动开发循环

**本Phase测试交付物**：

- `tests/test_xliff_generator.py`（XLIFF翻译单元/文件生成）

- `tests/test_xliff_validator.py`（XLIFF标准合规性验证）

---

## Phase 3: 多格式汇聚+自动探测+资源统一管理

### 📋 Phase 3 执行计划

#### 1. 概述与目标

- 实现输入格式自动探测引擎

- 实现图片资源统一管理（去重/命名/路径维护）

- 实现统一错误处理与报告生成

---

### 🧪 UTDD - 单元测试驱动

**测试交付物**: `tests/test_auto_detector.py`, `tests/test_resource_manager.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| `detect_format()` | DOCX文件识别<br>PPTX文件识别<br>PDF文件识别 | 扩展名错误<br>空文件 | 损坏文件伪装 |
| `manage_resources()` | 图片MD5去重<br>统一命名规则<br>路径维护 | 0图片<br>1000+图片 | 重复MD5冲突 |
| `generate_report()` | 转换统计报告<br>警告列表<br>错误详情 | 0警告0错误 | 大量错误处理 |

---

### ✅ ATDD - 验收测试驱动

#### 正常流程验收标准

1. 格式自动探测准确率100%

2. 图片去重率100%（相同图片不重复存储）

3. 资源路径引用100%正确

---

### 🔄 TDD - 测试驱动开发循环

**本Phase测试交付物**：

- `tests/test_auto_detector.py`（格式自动探测引擎）

- `tests/test_resource_manager.py`（图片资源统一管理）

---

## Phase 4: 用户体验+OPP→OL端到端集成+PyPI发布

### 📋 Phase 4 执行计划

#### 1. 概述与目标

- 完善CLI用户体验

- OPP→OL端到端集成测试

- PyPI发布准备

---

### 🧪 UTDD - 单元测试驱动

**测试交付物**: `tests/test_docx_e2e.py`, `tests/test_pptx_e2e.py`, `tests/test_pdf_e2e.py`, `tests/test_opp_ol_integration.py`

---

### ✅ ATDD - 验收测试驱动

#### 正常流程验收标准

1. DOCX/PPTX/PDF三格式端到端测试通过率100%

2. OPP输出→OL输入无缝对接，无需人工干预

3. PyPI包可一键安装，依赖自动解决

---

### 🎯 BDD - 行为驱动场景

**场景：结构化文档的完整本地化流水线**

Given：用户有一个 DOCX 格式的技术规格书 spec.docx（英文）

When：用户执行以下命令序列：

opp convert spec.docx --target-format both --output-dir preprocess/

ol translate preprocess/spec.xlf --target-lang ja-JP --output preprocess/spec_ja.xlf

ol apply-xliff preprocess/spec.md --xliff preprocess/spec_ja.xlf --output spec_ja.md

Then：

• spec_ja.md 为日文版技术规格书

• 所有排版格式与原始 MD 完全一致

• XLIFF翻译单元100%应用到对应位置

• 图片引用和路径保持不变

---

### 🔄 TDD - 测试驱动开发循环

**本Phase测试交付物**：

- `tests/test_docx_e2e.py`（DOCX通道端到端）

- `tests/test_pptx_e2e.py`（PPTX通道端到端）

- `tests/test_pdf_e2e.py`（PDF通道端到端）

- `tests/test_opp_ol_integration.py`（OPP→OL流水线集成）

---

## Phase 5: Office与数据格式扩展 (XLSX/CSV/JSON/XML)

### 📋 Phase 5 执行计划

#### 1. 概述与目标

- 扩展对电子表格与结构化数据的支持，实现 XLSX/CSV/JSON/XML 四种格式的提取

- 构建"表格通道"与"键值对通道"，将行列数据与嵌套结构映射为 MD 表格与 XLIFF 翻译单元

- 纯 Glue Coding：利用 pandas 和 openpyxl 处理表格，标准库处理 JSON/XML

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| XLSX 解析 | openpyxl / pandas | 读取工作表、单元格值（仅取值，忽略公式计算） |
| CSV 解析 | pandas | 编码推断、分隔符推断、结构化读取 |
| JSON 解析 | json (Stdlib) | 树状结构解析与扁平化 |
| XML 解析 | lxml / xml.etree | XPath 提取与节点遍历 |
| 表格通道 | 自研粘合层 | 将 DataFrame 统一转入 MD Generator 与 XLIFF Generator |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_xlsx_extractor.py`, `tests/test_csv_extractor.py`, `tests/test_json_extractor.py`, `tests/test_xml_extractor.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **XLSX/CSV核心提取器** | | | |
| `extract_tables()` | 多Sheet工作簿<br>带表头CSV<br>合并单元格XLSX | 单行/单列表格<br>100MB超大CSV<br>无表头CSV | 损坏的XLSX<br>密码保护Sheet<br>编码错误的CSV |
| **JSON核心提取器** | | | |
| `extract_key_values()` | 扁平JSON对象<br>嵌套对象<br>JSON数组 | 空JSON<br>单键值对<br>深度>10的嵌套 | 非法JSON格式<br>包含BOM头<br>循环引用对象 |
| **XML核心提取器** | | | |
| `extract_nodes()` | 标准配置XML<br>带命名空间XML<br>属性与文本混合 | 空XML<br>单节点XML<br>超长无换行XML | 标签未闭合<br>非法字符<br>DTD/XXE攻击载荷 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. XLSX/CSV：单元格/字段提取准确率 100%（50个标准样本）

2. JSON/XML：键名/节点路径作为上下文注释 100% 保留

3. 表格数据：完美映射为 MD 表格，XLIFF 按行生成 `<trans-unit>`

#### ❌ 异常流程验收标准

1. 损坏文件：自动识别并报告，不崩溃

2. 密码保护XLSX：提示"需要密码"并优雅退出

3. 编码错误：自动尝试 chardet/cchardet 推断，失败则提示

#### 🔲 边界条件验收标准

1. 表格行数上限：10,000 行（超出分页处理）

2. 嵌套深度：JSON/XML 嵌套 >8 层时自动截断并警告

3. 内存占用：流式读取 CSV，内存不随文件线性增长

#### ⚡ 非功能性验收标准

1. 提取性能：≥ 10MB/s（XLSX/CSV）

2. 依赖引入：仅增加 pandas, openpyxl, lxml

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：XLSX 多语言术语表转换**

Given：用户有一个 XLSX 术语表 glossary.xlsx (包含 Key, EN, ZH 三列)

When：用户执行 opp convert glossary.xlsx --target-format both

Then：

• MD 中生成标准 Markdown 表格，保留列结构

• XLIFF 中每一行生成一个 <trans-unit>

• Key 列的内容放入 <context> 或不可译属性中

**场景2：JSON 配置文件本地化**

Given：用户有一个 JSON 配置文件 ui_labels.json

When：用户执行 opp convert ui_labels.json --target-format xlf

Then：

• 键的路径 (如 "dashboard.menu.save") 作为 <trans-unit> 的 name 属性

• 值作为 source 文本

• 空值或数字类型自动跳过

---

### 🔄 TDD - 测试驱动开发循环

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| **🔴 红** | 先写四种数据提取器的测试用例 | 测试全部失败 |
| **🟢 绿** | 编写提取器代码，将数据转为内部统一结构 | 所有测试通过 |
| **🔄 重构** | 抽象 TableChannel 与 KeyValueChannel，复用 Phase 1/2 生成器 | 测试仍然全部通过 |

**本Phase测试交付物**：

- `tests/test_xlsx_extractor.py`

- `tests/test_csv_extractor.py`

- `tests/test_json_extractor.py`

- `tests/test_xml_extractor.py`

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| XLSX 公式取值问题 | 提取出公式字符串而非计算结果 | 统一使用 openpyxl data_only=True 模式读取 |
| CSV 方言多样 | 分隔符/引号解析失败 | 依赖 pandas 的智能推断引擎 pd.read_csv(sep=None) |
| XML 命名空间解析 | 无法定位节点 | 提取时自动剥离或保留命名空间映射表 |

---

## Phase 6: Web与电子书格式扩展 (HTML/EPUB)

### 📋 Phase 6 执行计划

#### 1. 概述与目标

- 扩展对网页与电子书的内容提取，实现 HTML/EPUB 到 MD/XLIFF 的转换

- 剥离网页噪音（导航栏、页脚），提取核心正文

- 纯 Glue Coding：利用 readability-lxml 或 docling 提取正文，markdownify 转 MD，ebooklib 解包 EPUB

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| HTML 正文 | readability-lxml / docling | 噪音剥离，核心DOM提取 |
| HTML→MD | markdownify | HTML 标签转 Markdown 语法 |
| EPUB 解包 | ebooklib | 遍历 spine/manifest，提取章节与资源 |
| 测试框架 | pytest | 单元测试 |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_html_extractor.py`, `tests/test_epub_extractor.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **HTML核心提取器** | | | |
| `extract_article()` | 新闻文章页<br>带代码块博客<br>多栏布局 | 单页应用<br>空 body<br>全 JS 渲染页 | 损坏 HTML<br>非 UTF-8 编码<br>恶意脚本 |
| **EPUB核心提取器** | | | |
| `extract_chapters()` | 多章节 EPUB<br>带内嵌图片<br>带脚注链接 | 单页 EPUB<br>无文字 EPUB<br>100MB超大书 | 损坏 ZIP 结构<br>加密 EPUB<br>缺失 OPF 文件 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. HTML：正文提取准确率 ≥ 95%（剔除导航/侧边栏）

2. EPUB：章节顺序与原书一致，图片引用路径 100% 正确

3. 格式保持：列表、表格、标题层级正确映射

#### ❌ 异常流程验收标准

1. 损坏文件：捕获解析异常，生成空 MD 并报告警告

2. JS 渲染页：提示"动态渲染页面可能提取不完整"

#### 🔲 边界条件验收标准

1. 文件大小：单 HTML 50MB，单 EPUB 200MB

2. 嵌套深度：HTML 深度嵌套表格自动降级

#### ⚡ 非功能性验收标准

1. 提取性能：≥ 5MB/s

2. 依赖轻量：不引入 Selenium/Playwright 等重型浏览器

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：产品文档 HTML 转换**

Given：用户有一个产品文档 HTML 页面 docs.html

When：用户执行 opp convert docs.html --target-format both

Then：

• 提取的内容不包含顶栏导航和页脚

• MD 中的代码块保持原语言标记

• 图片下载到本地并替换路径

**场景2：EPUB 电子书本地化**

Given：用户有一个 EPUB3 格式的小说 book.epub

When：用户执行 opp convert book.epub --target-format both

Then：

• MD 按章节生成二级标题

• XLIFF 按段落生成翻译单元，保留章节 ID

• 封面图片单独提取至 images/

---

### 🔄 TDD - 测试驱动开发循环

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| **🔴 红** | 先写 HTML/EPUB 提取器的测试 | 测试全部失败 |
| **🟢 绿** | 粘合 readability/markdownify/ebooklib 实现提取 | 所有测试通过 |
| **🔄 重构** | 统一 Web 资源下载逻辑与图片管理器 | 测试仍然全部通过 |

**本Phase测试交付物**：

- `tests/test_html_extractor.py`

- `tests/test_epub_extractor.py`

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| HTML 结构脏乱 | 提取出噪音文本 | 优先使用 docling 的深度学习正文提取，降级使用 readability |
| EPUB 内部路径复杂 | 图片引用 404 | 统一通过 ebooklib 提取二进制，交由 OPP ResourceManager 重命名管理 |

---

## Phase 7: 邮件与图像OCR扩展 (EML/MSG/Image)

### 📋 Phase 7 执行计划

#### 1. 概述与目标

- 补齐高频办公格式：EML/MSG 邮件，以及基于 OCR 的图片文本提取

- 对邮件：提取元数据（发件人/时间）、正文、附件（递归调用 OPP 处理）

- 对图片：调用 OCR 引擎提取文本，支持将扫描件作为输入源

- 纯 Glue Coding：使用 extract_msg 解析 MSG，email 标准库解析 EML，pytesseract / rapidocr 提取文字

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| MSG 解析 | extract_msg | 提取 Outlook MSG 元数据与正文 |
| EML 解析 | email (Stdlib) | 提取通用 MIME 邮件结构与内容 |
| OCR 引擎 | pytesseract / rapidocr-onnxruntime | 图片文字识别 |
| 图片处理 | Pillow | 图片预处理与格式转换 |

---

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_email_extractor.py`, `tests/test_image_ocr_extractor.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|---------|-------------|-----------|-------------|
| **Email核心提取器** | | | |
| `extract_email()` | 纯文本邮件<br>HTML正文邮件<br>带附件邮件 | 空正文邮件<br>超大附件(100MB+)<br>无主题邮件 | 损坏的MSG<br>编码错误的EML<br>加密邮件 |
| **Image OCR提取器** | | | |
| `extract_text_by_ocr()` | 打印文档截图<br>带标题PPT导出图<br>多栏扫描图 | 纯风景图(无文字)<br>低分辨率图<br>超大分辨率图(8K) | OCR引擎未安装<br>损坏的图片文件<br>0字节图片 |

---

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

#### 正常流程验收标准

1. Email：元数据（From/To/Date/Subject）100% 提取并作为上下文注释

2. Email：HTML 正文自动走 Phase 6 通道，纯文本走段落通道

3. Image OCR：可识别文字提取率 ≥ 95%（300dpi 英文/中文样本）

#### ❌ 异常流程验收标准

1. OCR 引擎缺失：自动降级为仅提取图片元数据，并输出安装指南

2. 附件格式不支持：保留原始二进制，在报告中列出

#### 🔲 边界条件验收标准

1. 邮件大小上限：500MB（含附件）

2. 图片分辨率：低于 72dpi 发出识别率降低警告

#### ⚡ 非功能性验收标准

1. OCR 可插拔：支持通过配置切换 Tesseract/RapidOCR/云端 API

2. 附件处理：递归解压深度 ≤ 3 层

---

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：业务邮件本地化**

Given：用户有一封 MSG 格式的业务更新通知 notice.msg

When：用户执行 opp convert notice.msg --target-format both

Then：

• MD 文件头部包含元数据 (发件人/时间等)

• 邮件正文正确转换为 MD

• 附件 (如 price_list.xlsx) 被提取并自动转换为对应的 MD/XLIFF

**场景2：扫描件 PNG 转换**

Given：用户有一张扫描的合同照片 contract.png

When：用户执行 opp convert contract.png --ocr-engine rapidocr

Then：

• MD 包含提取出的合同条款文本

• 图片本身保存至 images/ 目录

• XLIFF 按段落生成翻译单元

---

### 🔄 TDD - 测试驱动开发循环

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| **🔴 红** | 先写邮件与OCR提取测试 | 测试全部失败 |
| **🟢 绿** | 粘合 extract_msg/pytesseract 实现 | 所有测试通过 |
| **🔄 重构** | 抽象 AttachmentHandler，实现格式探测与递归调用 | 测试仍然全部通过 |

**本Phase测试交付物**：

- `tests/test_email_extractor.py`

- `tests/test_image_ocr_extractor.py`

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| OCR 识别率低 | 提取文本不可用 | 提供预处理参数配置（灰度化/二值化），支持多引擎结果对比 |
| 邮件编码混乱 | 乱码 | 优先使用 charset 正常解码，失败尝试 chardet 推断 |
| MSG 附件嵌套 | 死循环 | 限制递归深度，记录处理日志 |

---

## Phase 8: 富媒体与高级格式扩展 (v2.0 预留)

### 📋 Phase 8 执行计划

#### 1. 概述与目标

- 本 Phase 针对 Any2MD 支持的音视频、代码笔记本等长尾格式，作为后续版本的储备

- 预留对 Audio (WAV/MP3)、Video (MP4)、IPYNB (Jupyter Notebook)、YouTube URL 的支持

- 音视频主要提取语音转写文本；IPYNB 提取 Markdown 单元格与注释

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| 音视频转写 | whisper / docling[audio] | 语音识别为文本 |
| Jupyter | nbformat | 解析 Notebook JSON 结构 |
| URL 抓取 | markitdown[youtube] | 抓取字幕/元数据 |

---

### 🧪 UTDD - 单元测试驱动

| 核心函数 | 正常输入用例 | 异常输入用例 |
|---------|-------------|-------------|
| `transcribe_audio()` | 清晰英文录音<br>带环境噪音录音 | 损坏音频<br>无语音轨视频 |
| `extract_notebook_cells()` | 包含 MD/Code 的标准 Notebook | 损坏的 ipynb JSON |

---

### ✅ ATDD - 验收测试驱动

- 音频转写字错率 (CER) ≤ 10%

- Jupyter Notebook：Markdown 单元格 100% 提取，Code 单元格作为代码块保留

---

### 🎯 BDD - 行为驱动场景

**场景1：会议录音转换**

Given：用户有一个会议录音 meeting.mp3

When：用户执行 opp convert meeting.mp3 --target-format md --asr-engine whisper

Then：

• MD 文件包含按时间戳或段落分割的转写文本

---

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 依赖重型 (Whisper/PyTorch) | 安装包过大，用户流失 | 作为可选依赖 opp[audio]，提供云端 API 接入备选 |
| GPU 不可用 | 转写极慢 | 默认使用 whisper-cpp 或 tiny 模型 |

---

## 总体风险分析与缓解策略

| 风险等级 | 风险描述 | 影响范围 | 缓解策略 |
|----------|----------|----------|----------|
| 高 | PDF 布局解析不完美 | PDF 通道输出结构异常 | 布局检测后验证 + 降级策略 + 人工标注修正 |
| 高 | 复杂表格跨页/合并单元格 | 表格信息丢失或结构混乱 | 表格复杂度检测 + 超复杂表格降级处理 |
| 高 | 不同版本 Office 格式差异 | DOCX/PPTX/XLSX 解析遗漏 | 多版本样本收集 + 兼容性测试矩阵 |
| 高 | 新增依赖库过多导致冲突 | 整体项目环境 | 采用 extras 可选安装：`pip install opp[office,web,email]` |
| 中 | 扫描件 PDF OCR 质量不稳定 | PDF 通道提取质量 | 多 OCR 引擎支持 + OCR 质量自动评估 |
| 中 | 图片提取命名冲突或丢失 | 所有通道的资源管理 | UUID 命名 + MD5 去重 + 完整性校验 |
| 中 | OCR/ASR 引擎环境配置复杂 | Phase 7/8 | 提供 Docker 镜像，或默认使用轻量级 ONNX 模型 |
| 中 | 邮件附件格式无限延伸 | Phase 7 | 限制递归深度，未知格式直接保留二进制 |
| 低 | HTML 动态渲染内容丢失 | Phase 6 | 文档明确说明仅支持静态 HTML，动态需求建议用户先打印为 PDF |

---

## 里程碑总览与交付物

| 里程碑 | 阶段 | 核心交付物 | 预计工期 |
|--------|------|------------|----------|
| M0 | Phase 0：环境搭建 | 项目仓库、三格式提取器、UTDD测试矩阵、CI | 1 天 |
| M1 | Phase 1：MD通道输出 | BDD场景 + MD结构化生成 + 格式保护 | 1.5 天 |
| M2 | Phase 2：XLIFF通道输出 | ATDD四维验收标准 + XLIFF标准生成 + 验证器 | 1.5 天 |
| M3 | Phase 3：多格式汇聚 | TDD循环 + 自动探测 + 资源统一管理 | 1 天 |
| M4 | Phase 4：用户体验与集成 | BDD端到端测试 + PyPI发布 + OL流水线集成 | 1 天 |
| M5 | Phase 5：Office与数据扩展 | XLSX/CSV/JSON/XML 提取器 + 专用通道 | 1.5 天 |
| M6 | Phase 6：Web与电子书扩展 | HTML/EPUB 提取器 + 噪音剥离 | 1 天 |
| M7 | Phase 7：邮件与OCR扩展 | EML/MSG 提取器 + 附件递归 + OCR接入 | 1.5 天 |
| M8 | Phase 8：富媒体扩展 (v2.0) | 音视频转写 + Jupyter支持 (预留) | 2 天 |

**OPP 全功能总计预计工期：约 11.5 天 (不含 Phase 8 为 9.5 天)**

**总测试文件：约 45 个**

**总测试用例：约 450 个**

**测试覆盖率目标：≥ 90%**

---

*本计划合并自《OPP_DD_Vibe_Phase版.md》与《增补.txt》，版本号升级至 v4.0-Phase-Full。*
