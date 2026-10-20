"""Local HTML documentation; scientific implementations are never imported."""

project = "MCEG"
extensions = ["myst_parser", "sphinx.ext.graphviz"]
exclude_patterns = ["_build", "ja"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
myst_heading_anchors = 4
graphviz_output_format = "svg"
html_theme = "alabaster"
html_title = "MCEG: models and evidence"
html_theme_options = {"page_width": "1120px", "body_max_width": "850px"}
html_static_path = ["_generated/_static"]
html_css_files = ["mceg.css"]
