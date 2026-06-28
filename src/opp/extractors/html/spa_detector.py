"""SPA (Single Page Application) framework detection for HTML content.

Detects JS-heavy pages by matching framework/library signatures
in the HTML source. Used by HTMLExtractor to warn when content may
require JavaScript rendering to be visible.
"""

import re

# Pre-compiled SPA/JS framework detection patterns (AS-IS, 30 patterns)
_RE_JS_PATTERNS = [
    re.compile(r"react"),
    re.compile(r"vue"),
    re.compile(r"angular"),
    re.compile(r"ember\.js"),
    re.compile(r"mithril\.js"),
    re.compile(r"preact"),
    re.compile(r"solid\.js"),
    re.compile(r"svelte"),
    re.compile(r"jquery"),
    re.compile(r"prototype\.js"),
    re.compile(r"dojo"),
    re.compile(r"ext\.js"),
    re.compile(r" mootools"),
    re.compile(r"scriptaculous"),
    re.compile(r"node_modules"),
    re.compile(r"webpack"),
    re.compile(r"vite"),
    re.compile(r"next\.js"),
    re.compile(r"nuxt"),
    re.compile(r"gatsby"),
    re.compile(r"11ty"),
    re.compile(r"jekyll"),
    re.compile(r"hugo"),
    re.compile(r"angular\.js"),
    re.compile(r"underscore\.js"),
    re.compile(r"lazy\.js"),
    re.compile(r" lodash"),
]

_RE_SCRIPT_TAG_SIMPLE = re.compile(r"<script[^>]*>")


def detect_js_heavy(html_content: str) -> bool:
    """Detect if HTML content is JS-heavy (SPA framework).

    Checks both framework/library name heuristics in the raw HTML
    and script tag characteristics (long ``src=`` URLs suggest
    bundled applications).
    """
    content_lower = html_content.lower()
    for pattern in _RE_JS_PATTERNS:
        if pattern.search(content_lower):
            return True

        script_tags = _RE_SCRIPT_TAG_SIMPLE.findall(html_content)
    for tag in script_tags:
        if "src=" in tag and len(tag) > 50:
            return True

    return False
