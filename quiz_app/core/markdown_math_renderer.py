"""Markdown + LaTeX rendering helpers shared by Qt and web clients.

Architecture note:
    The renderer converts the same source markup into HTML and relies on
    MathJax at display-time. This keeps the rendering pipeline identical for
    Qt (via QWebEngineView) and the student browser page, preventing subtle
    discrepancies. A more advanced alternative would be to pre-render KaTeX or
    MathJax to static HTML during import time and cache the fragments inside
    the quiz data. That would reduce runtime work but would make quiz files
    larger and tightly couple storage with a specific math engine. For the
    prototype we prioritize flexibility, so every view requests a render and
    MathJax does the heavy lifting on the client.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from markdown_it import MarkdownIt

_MATHJAX_SCRIPT = (
    "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
)


@dataclass(slots=True)
class MarkdownMathRenderer:
    """Converts markdown-with-math into HTML fragments or full documents."""

    enable_html: bool = False
    _markdown: MarkdownIt = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._markdown = (
            MarkdownIt("commonmark", {"html": self.enable_html})
            .enable("table")
            .enable("strikethrough")
        )

    def render_fragment(self, markdown_text: str) -> str:
        """Render a markdown string into an HTML fragment."""

        sanitized = markdown_text.strip() or ""
        if not sanitized:
            return "<p><em>No content provided.</em></p>"
        return self._markdown.render(sanitized)

    def wrap_with_mathjax(self, body_html: str, title: str = "QuizQt") -> str:
        """Wrap a fragment inside a minimal HTML document that loads MathJax."""

        return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{title}</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 1rem; background: transparent; color: #f5f7ff; }}
      .question-html {{ font-size: 1.1rem; line-height: 1.5; }}
    </style>
    <script>
      window.MathJax = {{ tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }}, svg: {{ fontCache: 'global' }} }};
    </script>
    <script defer src=\"{_MATHJAX_SCRIPT}\"></script>
  </head>
  <body>
    <div class=\"question-html\">{body_html}</div>
  </body>
</html>"""

    def render_full_document(self, markdown_text: str, title: str = "QuizQt") -> str:
        """Convenience wrapper to render markdown and embed MathJax."""

        fragment = self.render_fragment(markdown_text)
        return self.wrap_with_mathjax(fragment, title=title)


renderer = MarkdownMathRenderer()
# Simple shared renderer instance to avoid rebuilding MarkdownIt. Safe for
# single-threaded Qt usage; FastAPI should either reuse it in a lock or create
# its own instance per process. MarkdownIt is thread-safe for read-only renders,
# so reusing this instance is acceptable for the current prototype, but we can
# swap to thread-local instances if high parallelism becomes necessary.
