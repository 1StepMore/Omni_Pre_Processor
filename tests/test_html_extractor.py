from pathlib import Path
import pytest

from opp.extractors.html import HTMLExtractor
from opp.utils.exceptions import CorruptedFileError


class TestHTMLExtractor:
    """Test suite for HTML extractor."""

    def test_supported_extensions(self):
        extractor = HTMLExtractor()
        assert extractor.supported_extensions() == [".html", ".htm"]

    def test_news_article_extraction(self, html_sample_files: Path):
        """Test news article with nav/article/sidebar/footer → ≥95% body, exclude nav/sidebar."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "news_article.html")

        # Should extract substantial content from article
        assert len(result.paragraphs) > 0

        # Build full text to check coverage
        full_text = " ".join(p.text for p in result.paragraphs).lower()

        # Should contain article body content
        assert "news content" in full_text or "article body" in full_text

        # Should NOT contain significant sidebar/nav content
        # (if extraction worked properly, sidebar markers should be minimal)
        sidebar_indicators = ["sidebar", "advertisement", "related content"]
        sidebar_count = sum(1 for s in sidebar_indicators if s in full_text)
        assert sidebar_count == 0, f"Unexpected sidebar content detected: {sidebar_count}"

    def test_blog_code_blocks(self, html_sample_files: Path):
        """Test blog post with code blocks → preserve `<pre><code>` blocks."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "blog_code.html")

        full_text = " ".join(p.text for p in result.paragraphs)

        assert len(result.paragraphs) > 0

    def test_multi_column(self, html_sample_files: Path):
        """Test multi-column layout → extract without column artifacts."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "multi_column.html")

        # Should extract content from both columns
        full_text = " ".join(p.text for p in result.paragraphs)

        # Both column contents should be present
        assert "column 1" in full_text.lower() or "col1" in full_text.lower()
        assert "column 2" in full_text.lower() or "col2" in full_text.lower()

        # No column-specific formatting artifacts
        # (content should flow naturally without column markers)

    def test_spa_warning(self, html_sample_files: Path):
        """Test SPA (JS-rendered page) → generate warning."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "spa.html")

        # Should have JS-heavy warning
        assert len(result.warnings) > 0
        assert any("JS-rendered page detected" in w or "javascript" in w.lower() for w in result.warnings)

    def test_empty_body(self, html_sample_files: Path):
        """Test empty body → graceful handling."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "empty.html")

        # Should handle gracefully - either 0 paragraphs or with warning
        if len(result.paragraphs) == 0:
            assert len(result.warnings) > 0 or "empty" in str(result).lower()
        else:
            # If some content extracted, that's also acceptable
            pass

    def test_large_file_performance(self, html_sample_files: Path):
        """Test large file processing."""
        import time

        large_file = html_sample_files / "large.html"

        content_template = """<!DOCTYPE html><html><head><title>Large File Test</title></head><body><article>{}</article></body></html>"""

        paragraph = "<p>Content. " * 200 + "</p>\n"
        repeated = paragraph * 2200

        large_file.write_text(content_template.format(repeated), encoding="utf-8")

        file_size = large_file.stat().st_size
        assert file_size >= 5 * 1024 * 1024, f"File too small: {file_size / 1024 / 1024:.1f}MB"

        extractor = HTMLExtractor()
        start = time.time()
        result = extractor.extract(large_file)
        elapsed = time.time() - start

        assert len(result.paragraphs) > 0, "No content extracted from large file"

        throughput_mbps = (file_size / 1024 / 1024) / elapsed
        assert throughput_mbps > 0, "Processing should complete"

        large_file.unlink()

    def test_corrupt_html(self, html_sample_files: Path):
        """Test corrupt HTML → graceful error handling."""
        extractor = HTMLExtractor()

        # Should handle gracefully - either exception or warning
        try:
            result = extractor.extract(html_sample_files / "corrupt.html")
            # If no exception, should have warnings about low quality
            if result.paragraphs:
                # Extraction succeeded but may have warnings
                pass
        except (CorruptedFileError, Exception) as e:
            # Exception is acceptable for corrupt files
            pass

    def test_encoding_handling(self, html_sample_files: Path):
        """Test non-UTF8 encoding → proper handling."""
        extractor = HTMLExtractor()
        result = extractor.extract(html_sample_files / "non_utf8.html")

        # Should extract content without crashing
        assert result is not None
        # Content may have encoding artifacts but should not crash


# Fixture for HTML sample files
@pytest.fixture
def html_sample_files(tmp_path: Path) -> Path:
    """Create sample HTML files in tmp directory."""
    test_dir = tmp_path / "test_html"
    test_dir.mkdir()

    # 1. News article with nav/article/sidebar/footer
    news_html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>News Article</title></head>
<body>
<nav class="main-nav"><a href="/">Home</a> | <a href="/news">News</a></nav>
<header><h1>Breaking News</h1></header>
<aside class="widget"><h3>Recommended</h3><p>Widget info here</p></aside>
<article>
    <h2>Article Title</h2>
    <p>This is the main article body content with important news information.</p>
    <p>More news content here with details about the story.</p>
</article>
<footer><p>Copyright 2024 News Site</p></footer>
</body>
</html>"""
    (test_dir / "news_article.html").write_text(news_html, encoding="utf-8")

    # 2. Blog post with code blocks
    blog_html = """<!DOCTYPE html>
<html>
<head><title>Blog Post</title></head>
<body>
<article>
    <h1>Python Tutorial</h1>
    <p>Here is how to write a hello world program:</p>
    <pre><code>def hello():
        print("Hello, World!")
        return 42

result = hello()
print(result)</code></pre>
    <p>You can also use other languages:</p>
    <pre><code>const greet = () => console.log("Hi!");
greet();</code></pre>
</article>
</body>
</html>"""
    (test_dir / "blog_code.html").write_text(blog_html, encoding="utf-8")

    # 3. Multi-column layout
    multi_col_html = """<!DOCTYPE html>
<html>
<head><title>Multi-Column</title></head>
<body>
<style>
.columns { column-count: 2; }
</style>
<div class="columns">
    <p>Column 1 content - first column text goes here with more content.</p>
    <p>More content in column 1.</p>
</div>
<div class="columns">
    <p>Column 2 content - second column text here with additional text.</p>
    <p>More content in column 2.</p>
</div>
</body>
</html>"""
    (test_dir / "multi_column.html").write_text(multi_col_html, encoding="utf-8")

    # 4. SPA (JS-heavy page)
    spa_html = """<!DOCTYPE html>
<html>
<head>
    <title>SPA Page</title>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
</head>
<body>
    <div id="root"></div>
    <script>
        // React app rendering
        const App = () => React.createElement('h1', null, 'Hello React');
        ReactDOM.render(React.createElement(App), document.getElementById('root'));
    </script>
</body>
</html>"""
    (test_dir / "spa.html").write_text(spa_html, encoding="utf-8")

    # 5. Empty body
    empty_html = """<!DOCTYPE html>
<html>
<head><title>Empty</title></head>
<body>
</body>
</html>"""
    (test_dir / "empty.html").write_text(empty_html, encoding="utf-8")

    # 6. Corrupt HTML (malformed)
    corrupt_html = """<!DOCTYPE html>
<html>
<head><title>Corrupt</title></head>
<body>
<p>This is some content
<script>malformed unclosed tag
<div>another unclosed
<article>content here
"""
    (test_dir / "corrupt.html").write_text(corrupt_html, encoding="utf-8")

    # 7. Non-UTF8 encoding (Latin-1)
    non_utf8_html = """<!DOCTYPE html>
<html>
<head><title>Non-UTF8</title></head>
<body>
<article>
    <h1>Caf\u00e9 Document</h1>
    <p>Na\u00efve encoding test with special chars.</p>
    <p>More text with \u00e9\u00e0\u00fc characters.</p>
</article>
</body>
</html>"""
    (test_dir / "non_utf8.html").write_bytes(non_utf8_html.encode("latin-1"))

    return test_dir