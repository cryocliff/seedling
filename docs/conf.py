"""Sphinx configuration for the seedling documentation site.

The docs are the same Markdown files the repo already ships
(DOCUMENTATION.md, OFFLINE.md) -- MyST-Parser renders them and
sphinxcontrib-mermaid turns the ```mermaid fences into diagrams, so there's
no separate source of truth to keep in sync. Built and published to GitHub
Pages by .github/workflows/docs.yml; build locally with:

    uv venv && uv pip install -r docs/requirements.txt
    uv run sphinx-build -b html docs docs/_build/html
"""

from __future__ import annotations

project = "seedling"
author = "seedling contributors"
copyright = "seedling contributors"

extensions = [
    "myst_parser",
    "sphinxcontrib.mermaid",
]

# --- Markdown handling (MyST) ---------------------------------------------
# Turn fenced ```mermaid blocks into the mermaid directive (so the same
# fences that render on GitHub also render here), and auto-generate
# GitHub-style heading anchors so the in-page "Contents" links resolve.
myst_fence_as_directive = ["mermaid"]
myst_heading_anchors = 4
myst_enable_extensions = ["colon_fence", "deflist"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# --- HTML output ----------------------------------------------------------
html_theme = "furo"
html_title = "seedling"
