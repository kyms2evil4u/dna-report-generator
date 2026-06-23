"""
Standalone HTML Report Generator using Jinja2.
Produces a self-contained, interactive HTML file with embedded CSS/JS.
"""

import os
import json
from typing import Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def generate_html_report(report_data: Dict, output_path: str) -> str:
    """
    Render the report as a standalone HTML file.
    Returns the output path.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )

    # Register custom filters
    def format_number(value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return value
    env.filters["format_number"] = format_number

    template = env.get_template("report.html")

    # Serialize data for JavaScript embedding
    report_json = json.dumps(report_data, default=str)

    html_content = template.render(
        report=report_data,
        report_json=report_json,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
