# OPP production matrix — formats × extraction × MCP tools (issue OPP#112)

Derived truth: input formats: **16** · MCP tools: **9** · extractor classes: **16**
（计数由 `scripts/coverage_matrix.py --check` 与源码派生值比对；
`scripts/doc_inventory.py --check` 门禁 README/AGENTS 的对应声明。）

标注含义：✅ 主路径可用 · ⚠️ 可用但依赖可选包/外部二进制（缺省时优雅降级）
· ❌ 不支持。

## Format coverage

| 格式 | 提取（CLI/MCP 共用 extractor） | MCP `extract_document` | 备注（错误处理 / 依赖） |
|------|-------------------------------|------------------------|--------------------------|
| `docx` | ✅ DOCXExtractor | ✅ | 结构化提取 + floating image（见 `src/opp/extractors/docx.py`） |
| `pptx` | ✅ PPTXExtractor | ✅ | slide 文本 + 表格 |
| `pdf` | ✅ PDFExtractor / PDF2HTMLExtractor | ✅ | 双引擎；PDF→XLIFF 按设计拒绝（见 ACCEPTED_GAPS） |
| `xlsx` | ✅ XLSXExtractor | ✅ | 单元格表 + `xliff_map.json` 骨架（OPP#94） |
| `csv` | ✅ CSVExtractor | ✅ | 表格 → MD 表 |
| `json` | ✅ JSONExtractor | ✅ | key=value 扁平化 |
| `xml` | ✅ XMLExtractor | ✅ | |
| `html` | ✅ HTMLExtractor | ✅ | skeleton_html 打包（OPP#92） |
| `epub` | ✅ EPUBExtractor | ✅ | spine 顺序 + skeleton（OPP#39） |
| `eml` | ✅ EmailExtractor | ✅ | 单 trans-unit（多段拆分见 OPP EML 轮）；skeleton（OPP EML 2026-10-27） |
| `msg` | ⚠️ EmailExtractor（`_extract_msg`） | ⚠️ | 需可选包 `extract-msg`；缺省时该格式优雅跳过 |
| `image` | ⚠️ ImageOCRExtractor | ⚠️ | OCR 依赖 `pytesseract` + tesseract 二进制；缺 Pillow/tesseract 时降级 |
| `audio` | ⚠️ AudioExtractor | ⚠️ | 转写依赖外部转写栈（whisper 类）；缺省降级 |
| `video` | ⚠️ VideoExtractor | ⚠️ | 音轨抽取 + 转写；依赖 ffmpeg 与转写栈 |
| `youtube` | ⚠️ YouTubeExtractor | ⚠️ | 需网络 + `yt-dlp` 类下载器 |
| `ipynb` | ⚠️ IPYNBExtractor | ⚠️ | 需可选包 `nbformat`；ImportError 时降级 |

## MCP tools（9，全部被场景库覆盖 — 套件 coverage_audit 的 orf/opp 行）

| 工具 | 能力域 | 矩阵关系 |
|------|--------|----------|
| `extract_document` | 单文档提取（全部 16 格式，MD/XLIFF/both） | 上表「提取」列的 MCP 面 |
| `batch_extract` | 目录批量提取 | 复用同一 extractor 注册表 |
| `detect_format_tool` | 魔数格式检测 | 提取前置 |
| `generate_markdown` | 生成 MD 产物 | MD 输出格式 |
| `generate_xliff` | 生成 XLIFF 产物 | XLIFF 输出格式 |
| `save_skeleton` | skeleton.zip 落盘（OPP#39/#92/#94 + EML） | ORF `apply_xliff` 的前置 |
| `validate_xliff` | XLIFF 校验 | 质量面 |
| `get_capabilities` | 运行时能力自述 | 本矩阵的机器源 |
| `ping` | 健康检查 | — |

## 错误处理

结构化错误体系在 `src/opp/error_handler.py`：`OPPError` 基类 +
`DetectionError` / `ExtractionError` / `ResourceError` / `ExportError`；
CLI 非零退出 + MCP 工具返回结构化 error envelope（`OPP_INVALID_INPUT` /
`PATH_NOT_ALLOWED` 等），详见 `docs/API.md`。
