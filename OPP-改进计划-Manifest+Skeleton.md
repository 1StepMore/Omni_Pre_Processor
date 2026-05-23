# OPP 改进计划：Manifest + Skeleton 支持

**版本**: v1.0
**目标**: 为 OPP→OL→ORF 流水线提供显式元数据支持
**生效日期**: 2026年5月

---

## 1. 背景与目标

### 1.1 为什么需要这些改动

当前 OPP 的输出只有纯文件（MD、XLIFF、图片），没有任何元数据描述：
- 下游 ORF 不知道源文件格式是什么
- 无法追踪 MD5 去重后的图片映射关系
- XLIFF→DOCX 回填缺少原始 skeleton 文件

### 1.2 改动范围

| 改动项 | 文件 | 优先级 |
|--------|------|--------|
| manifest.json 生成 | `cli.py` | 🔴 高 |
| ExtractionResult 新增 skeleton 字段 | `utils/dataclasses.py` | 🔴 高 |
| DOCX extractor 支持 skeleton | `extractors/docx.py` | 🔴 高 |
| PPTX extractor 支持 skeleton | `extractors/pptx.py` | 🔴 高 |
| Pipeline 保存 skeleton.zip | `pipeline.py` | 🔴 高 |
| Manifest 中加入 skeleton 路径 | `cli.py` | 🟡 中 |

---

## 2. 方案一：manifest.json 生成

### 2.1 目标

在 OPP 输出目录生成 `{base_name}_manifest.json`，记录：
- 源文件信息（路径、格式、大小、MD5）
- 输出文件信息（MD、XLIFF 路径及统计）
- 图片资源信息
- 提取元数据

### 2.2 注入点

**文件**: `/mnt/d/贯维/Omni_Pre_Processor/src/opp/cli.py`
**函数**: `process_single_file()`
**位置**: 在 `generate_xliff()` 调用之后，return 之前（约 line 212-213）

### 2.3 实现代码

在 `cli.py` 顶部添加辅助函数：

```python
# ========== OPP manifest.json 支持 ==========

import json
import hashlib
from datetime import datetime
from pathlib import Path

def _detect_format_from_extension(path: Path) -> str:
    """从文件扩展名推断格式类型"""
    ext = path.suffix.lower()
    format_map = {
        ".docx": "DOCX",
        ".pptx": "PPTX",
        ".pdf": "PDF",
        ".xlsx": "XLSX",
        ".html": "HTML",
        ".xml": "XML",
        ".json": "JSON",
        ".csv": "CSV",
        ".epub": "EPUB",
        ".eml": "EML",
        ".msg": "MSG",
        ".md": "MARKDOWN",
        ".xlf": "XLIFF",
        ".xliff": "XLIFF",
    }
    return format_map.get(ext, "UNKNOWN")

def _compute_file_md5(path: Path) -> str:
    """计算文件的 MD5 哈希"""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()

def _count_xliff_units(xliff_path: Path) -> int:
    """统计 XLIFF 文件中的 trans-unit 数量"""
    import re
    content = xliff_path.read_text(encoding="utf-8")
    return len(re.findall(r'<trans-unit[^>]*>', content))

def get_opp_version() -> str:
    """获取 OPP 版本号"""
    try:
        from opp import __version__
        return __version__
    except ImportError:
        return "0.1.0"
```

在 `process_single_file()` 函数末尾，在 `return True` 之前添加：

```python
# ========== 生成 manifest.json ==========

md_path = output_dir / f"{base_name}.md"
xliff_path = output_dir / f"{base_name}.xlf"

manifest = {
    "manifest_version": "1.0",
    "generated_at": datetime.now().isoformat() + "Z",
    "tool": "OPP",
    "tool_version": get_opp_version(),

    "source": {
        "file_path": str(file_path.resolve()),
        "original_filename": file_path.name,
        "format": _detect_format_from_extension(file_path),
        "file_size_bytes": file_path.stat().st_size,
        "file_hash_md5": _compute_file_md5(file_path),
    },

    "extraction": {
        "source_lang": args.source_lang or "en",
        "target_lang": args.target_lang or "en",
        "outputs": {
            "markdown": {
                "path": str(md_path.relative_to(output_dir)) if md_path.exists() else None,
                "paragraph_count": len(proc_result.extraction_result.paragraphs) if proc_result.extraction_result else 0,
                "table_count": len(proc_result.extraction_result.tables) if proc_result.extraction_result else 0,
            },
            "xliff": {
                "path": str(xliff_path.relative_to(output_dir)) if xliff_path.exists() else None,
                "trans_unit_count": _count_xliff_units(xliff_path) if xliff_path.exists() else 0,
            }
        },
        "images": [
            {
                "mime_type": img.mime_type,
                "width": img.width,
                "height": img.height,
                "data_size_bytes": len(img.data),
            }
            for img in (proc_result.extraction_result.images if proc_result.extraction_result else [])
        ],
        "warnings": proc_result.extraction_result.warnings if proc_result.extraction_result else [],
    },

    "resources": {
        "storage_dir": str(args.resource_dir.resolve()) if args.resource_dir else str(Path.cwd() / "resources"),
        "image_count": len(proc_result.extraction_result.images) if proc_result.extraction_result else 0,
    },
}

manifest_path = output_dir / f"{base_name}_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

logger.info(f"Manifest written: {manifest_path}")
```

### 2.4 预期输出

生成文件：`{output_dir}/{base_name}_manifest.json`

```json
{
  "manifest_version": "1.0",
  "generated_at": "2026-05-22T14:30:00Z",
  "tool": "OPP",
  "tool_version": "0.1.0",
  "source": {
    "file_path": "/home/user/docs/spec.docx",
    "original_filename": "spec.docx",
    "format": "DOCX",
    "file_size_bytes": 45824,
    "file_hash_md5": "a1b2c3d4e5f6..."
  },
  "extraction": {
    "source_lang": "en",
    "target_lang": "zh",
    "outputs": {
      "markdown": {
        "path": "spec.md",
        "paragraph_count": 150,
        "table_count": 3
      },
      "xliff": {
        "path": "spec.xlf",
        "trans_unit_count": 42
      }
    },
    "images": [
      {
        "mime_type": "image/png",
        "width": 800,
        "height": 600,
        "data_size_bytes": 24580
      }
    ],
    "warnings": []
  },
  "resources": {
    "storage_dir": "resources",
    "image_count": 5
  }
}
```

### 2.5 验证测试

```python
# tests/test_manifest_generation.py

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from opp.cli import process_single_file
from opp.utils.dataclasses import ExtractionResult, ImageData, DocumentMetadata

def test_manifest_generates_for_md_output(tmp_path):
    """测试 MD 输出时生成 manifest.json"""
    # Setup
    input_file = tmp_path / "test.docx"
    input_file.write_bytes(b"fake docx content")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Mock args
    args = MagicMock()
    args.files = [input_file]
    args.output_dir = output_dir
    args.target_format = "md"
    args.source_lang = "en"
    args.target_lang = "zh"
    args.resource_dir = tmp_path / "resources"
    args.resource_dir.mkdir()

    # Execute
    # ... (call process_single_file with mocked pipeline)

    # Assert
    manifest_path = output_dir / "test_manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["manifest_version"] == "1.0"
    assert manifest["source"]["original_filename"] == "test.docx"
    assert manifest["source"]["format"] == "DOCX"
    assert manifest["extraction"]["source_lang"] == "en"
    assert manifest["extraction"]["target_lang"] == "zh"
    assert manifest["extraction"]["outputs"]["markdown"]["path"] == "test.md"

def test_manifest_generates_for_xlf_output(tmp_path):
    """测试 XLIFF 输出时生成 manifest.json"""
    # 类似测试，验证 xliff 输出信息

def test_manifest_captures_image_info(tmp_path):
    """测试 manifest 包含图片信息"""
    # 验证 images 数组包含 mime_type, width, height, data_size_bytes

def test_manifest_captures_warnings(tmp_path):
    """测试 manifest 包含警告信息"""
    # 验证 warnings 数组被正确记录
```

---

## 3. 方案二：Skeleton 保存支持

### 3.1 目标

保存原始 DOCX/PPTX 的完整 OOXML ZIP 结构（`.skeleton.zip`），供后续 ORF 的 XLIFF→DOCX/PPTX 回填使用。

### 3.2 修改 ExtractionResult

**文件**: `/mnt/d/贯维/Omni_Pre_Processor/src/opp/utils/dataclasses.py`

```python
# 在 ExtractionResult dataclass 中添加两个新字段:

@dataclass
class ExtractionResult:
    paragraphs: List[ParagraphData]
    tables: List[TableData]
    images: List[ImageData]
    attachments: List[AttachmentData] = field(default_factory=list)
    metadata: Optional[DocumentMetadata] = None
    warnings: List[str] = field(default_factory=list)
    is_transcription: bool = False

    # === 新增字段 ===
    skeleton: Optional[bytes] = None  # 原始 OOXML ZIP 完整内容
    skeleton_files: Optional[List[str]] = None  # ZIP 内的关键文件列表
```

### 3.3 修改 DOCX Extractor

**文件**: `/mnt/d/贯维/Omni_Pre_Processor/src/opp/extractors/docx.py`

```python
import zipfile
# ... existing imports ...

def extract(self, input_path: Path) -> ExtractionResult:
    # ... existing validation and extraction code (lines 25-60) ...

    # === 新增: Skeleton 保存 ===
    skeleton_bytes: Optional[bytes] = None
    skeleton_files: Optional[List[str]] = None

    try:
        with zipfile.ZipFile(input_path, 'r') as zf:
            # 读取完整 ZIP 作为字节流
            skeleton_bytes = zf.read()

            # 记录关键 OOXML 文件（用于调试/验证）
            key_files = [
                'word/document.xml',      # 主文档内容
                'word/styles.xml',         # 样式定义
                'word/numbering.xml',     # 编号定义
                'word/settings.xml',      # 文档设置
                '[Content_Types].xml',   # 内容类型声明
            ]
            skeleton_files = [f for f in key_files if f in zf.namelist()]

    except zipfile.BadZipFile:
        warnings.append("Skeleton extraction failed: not a valid ZIP/DOCX file")
        skeleton_bytes = None
        skeleton_files = None

    return ExtractionResult(
        paragraphs=paragraphs,
        tables=tables,
        images=images,
        metadata=metadata,
        warnings=warnings,
        is_transcription=is_transcription,
        # === 新增返回值 ===
        skeleton=skeleton_bytes,
        skeleton_files=skeleton_files,
    )
```

### 3.4 修改 PPTX Extractor

**文件**: `/mnt/d/贯维/Omni_Pre_Processor/src/opp/extractors/pptx.py`

```python
import zipfile
# ... existing imports ...

def extract(self, input_path: Path) -> ExtractionResult:
    # ... existing extraction code (lines 29-70) ...

    # === 新增: Skeleton 保存 ===
    skeleton_bytes: Optional[bytes] = None
    skeleton_files: Optional[List[str]] = None

    try:
        with zipfile.ZipFile(input_path, 'r') as zf:
            skeleton_bytes = zf.read()

            # PPTX 关键文件（列出所有 ppt/ 下的文件）
            skeleton_files = [f for f in zf.namelist() if f.startswith('ppt/')]

    except zipfile.BadZipFile:
        warnings.append("Skeleton extraction failed: not a valid ZIP/PPTX file")
        skeleton_bytes = None
        skeleton_files = None

    return ExtractionResult(
        paragraphs=all_paragraphs,
        tables=[],
        images=images,
        metadata=metadata,
        warnings=warnings,
        is_transcription=is_transcription,
        # === 新增返回值 ===
        skeleton=skeleton_bytes,
        skeleton_files=skeleton_files,
    )
```

### 3.5 修改 Pipeline 保存 skeleton.zip

**文件**: `/mnt/d/贯维/Omni_Pre_Processor/src/opp/pipeline.py`

在 `OPPPipeline` 类中添加新方法：

```python
def save_skeleton(self, result: ExtractionResult, base_name: str, output_dir: Path) -> Optional[Path]:
    """保存 skeleton ZIP 文件

    Args:
        result: ExtractionResult，包含 skeleton 字节数据
        base_name: 输出文件基础名
        output_dir: 输出目录

    Returns:
        skeleton 文件路径，或 None（如果无 skeleton）
    """
    if not result or not result.skeleton:
        return None

    skeleton_path = output_dir / f"{base_name}.skeleton.zip"

    try:
        with open(skeleton_path, "wb") as f:
            f.write(result.skeleton)
        self.logger.info(f"Skeleton saved: {skeleton_path}")
        return skeleton_path
    except IOError as e:
        self.logger.warning(f"Failed to save skeleton: {e}")
        return None
```

然后在 `run()` 或 `process_single_file()` 流程中调用。找到 `generate_markdown()` 和 `generate_xliff()` 之后添加：

```python
# 在 generate_xliff() 之后添加:
skeleton_path = self.save_skeleton(
    proc_result.extraction_result,
    base_name,
    output_dir
)
```

### 3.6 修改 cli.py Manifest 加入 skeleton 信息

在 2.3 节的 manifest 生成代码中，在 `"resources"` 节之后或单独添加：

```python
# skeleton 信息（如果有）
if skeleton_path:
    manifest["skeleton"] = {
        "path": str(skeleton_path.relative_to(output_dir)),
        "format": "ZIP",
        "key_files": proc_result.extraction_result.skeleton_files,
    }
```

### 3.7 预期输出

```
output_dir/
├── spec.md              # 提取的 Markdown
├── spec.xlf            # 提取的 XLIFF
├── spec_manifest.json   # 元数据清单
└── spec.skeleton.zip   # 原始 DOCX/PPTX 的完整 ZIP 结构
```

验证 skeleton.zip 内容：

```bash
unzip -l spec.skeleton.zip
# Archive contains:
#   [Content_Types].xml
#   _rels/.rels
#   docProps/app.xml
#   docProps/core.xml
#   word/document.xml
#   word/styles.xml
#   word/numbering.xml
#   word/settings.xml
#   ...
```

### 3.8 验证测试

```python
# tests/test_skeleton_preservation.py

import pytest
import zipfile
from pathlib import Path
from opp.extractors.docx import DOCXExtractor
from opp.extractors.pptx import PPTXExtractor

def test_docx_extractor_preserves_skeleton(tmp_path):
    """测试 DOCX extractor 保存 skeleton"""
    # Create a minimal DOCX
    from docx import Document
    doc = Document()
    doc.add_heading("Test")
    doc.add_paragraph("Content")
    docx_path = tmp_path / "test.docx"
    doc.save(str(docx_path))

    # Extract
    extractor = DOCXExtractor()
    result = extractor.extract(docx_path)

    # Assert skeleton exists
    assert result.skeleton is not None
    assert result.skeleton_files is not None
    assert 'word/document.xml' in result.skeleton_files
    assert '[Content_Types].xml' in result.skeleton_files

    # Verify ZIP is valid
    import io
    with zipfile.ZipFile(io.BytesIO(result.skeleton), 'r') as zf:
        assert 'word/document.xml' in zf.namelist()
        doc_xml = zf.read('word/document.xml')
        assert b"Test" in doc_xml

def test_pptx_extractor_preserves_skeleton(tmp_path):
    """测试 PPTX extractor 保存 skeleton"""
    # Create minimal PPTX
    from pptx import Presentation
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[0])
    pptx_path = tmp_path / "test.pptx"
    prs.save(str(pptx_path))

    extractor = PPTXExtractor()
    result = extractor.extract(pptx_path)

    assert result.skeleton is not None
    assert any(f.startswith('ppt/') for f in result.skeleton_files)

def test_skeleton_saved_to_file(tmp_path):
    """测试 skeleton 被正确写入文件"""
    # ... test pipeline.save_skeleton() ...

def test_skeleton_zip_valid_and_parseable(tmp_path):
    """测试保存的 ZIP 可被正确解压和解析"""
    # ... integration test ...

def test_invalid_doc_returns_no_skeleton(tmp_path):
    """测试无效文件不返回 skeleton"""
    invalid_file = tmp_path / "invalid.docx"
    invalid_file.write_bytes(b"not a valid docx")

    extractor = DOCXExtractor()
    result = extractor.extract(invalid_file)

    assert result.skeleton is None
    assert "Skeleton extraction failed" in result.warnings[-1]
```

---

## 4. 风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| Skeleton 文件过大（50MB+） | 占用磁盘空间 | 添加 `--no-skeleton` CLI 选项禁用 |
| Skeleton 包含敏感元数据 | 信息泄露 | 可选：保存前清理 `docProps/core.xml` 中的作者信息 |
| 旧版 .doc 格式无法提取 | 部分文件无 skeleton | 添加 try/except 并记录警告，不阻塞流程 |
| python-docx 已修改 internal XML | skeleton 不完整 | 验证 ZIP 包含 `word/document.xml` |

---

## 5. 实施检查清单

### 阶段一：manifest.json（预计 1-2 小时）

- [ ] 在 `cli.py` 添加辅助函数（`_detect_format_from_extension`, `_compute_file_md5`, `_count_xliff_units`, `get_opp_version`）
- [ ] 在 `process_single_file()` 末尾添加 manifest 生成代码
- [ ] 验证 `opp convert spec.docx --target-format md` 生成 `spec_manifest.json`
- [ ] 验证 manifest 内容正确（源文件、输出路径、图片信息）
- [ ] 添加单元测试 `tests/test_manifest_generation.py`
- [ ] 运行现有测试确保无回归

### 阶段二：skeleton 支持（预计 0.5-1 天）

- [ ] 在 `utils/dataclasses.py` 的 `ExtractionResult` 添加 `skeleton` 和 `skeleton_files` 字段
- [ ] 修改 `extractors/docx.py` 添加 zipfile 读取逻辑
- [ ] 修改 `extractors/pptx.py` 添加 zipfile 读取逻辑
- [ ] 在 `pipeline.py` 添加 `save_skeleton()` 方法
- [ ] 在 `cli.py` manifest 中加入 skeleton 路径
- [ ] 验证 `spec.skeleton.zip` 生成且包含有效 ZIP
- [ ] 验证 ZIP 内 `word/document.xml` 包含原始文本
- [ ] 添加单元测试 `tests/test_skeleton_preservation.py`
- [ ] 运行现有测试确保无回归

---

## 6. 向后兼容性说明

| 改动 | 影响 | 缓解 |
|------|------|------|
| ExtractionResult 新增字段 | Python dataclass 支持默认值，不破坏现有代码 | 使用 `Optional[bytes] = None` |
| cli.py 新增 manifest 生成 | 只新增文件，不影响现有输出 | 用户不感知，除非查看输出目录 |
| pipeline.py 新增方法 | 不影响现有流程 | `save_skeleton()` 返回 None 时不写入文件 |

---

## 7. 未来扩展

1. **Skeleton 选择性保存**：添加 `--skeleton-mode full|minimal|none` 选项
2. **Skeleton 压缩**：对 skeleton.zip 使用 `zipfile.ZIP_DEFLATED` 压缩
3. **元数据清理**：保存前移除 `docProps/core.xml` 中的敏感字段
4. **多文件 Batch manifest**：支持批量处理时的汇总 manifest
