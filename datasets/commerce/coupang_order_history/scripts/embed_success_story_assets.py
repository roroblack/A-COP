#!/usr/bin/env python3
"""Embed SUCCESS_STORY screenshot assets as PNG data URIs for one-file publishing."""

from __future__ import annotations

import base64
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "SUCCESS_STORY.html"
BLOGGER_REPORT = ROOT / "SUCCESS_STORY_BLOGGER.html"

IMAGE_PATTERN = re.compile(
    r'(?P<prefix><img\s+[^>]*?src=")'
    r'(?P<path>report_assets/success_story/[^"<>]+\.png)'
    r'(?P<suffix>"[^>]*>)',
    re.IGNORECASE,
)


def embed(match: re.Match[str]) -> str:
    image_path = ROOT / Path(match.group("path"))
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f'{match.group("prefix")}data:image/png;base64,{payload}{match.group("suffix")}'


def scope_css_for_blogger(css: str) -> str:
    """Scope report CSS to one Blogger post and drop standalone-only rules."""
    scoped: list[str] = []
    skip_dialog_rule = False
    for line in css.splitlines():
        stripped = line.strip()
        if stripped.startswith("dialog"):
            skip_dialog_rule = "}" not in stripped
            continue
        if skip_dialog_rule:
            if "}" in stripped:
                skip_dialog_rule = False
            continue
        if stripped.startswith("html {"):
            continue
        if stripped.startswith(":root {"):
            scoped.append(line.replace(":root", ".csb", 1))
            continue
        if stripped.startswith("body {"):
            scoped.append(line.replace("body", ".csb", 1))
            continue
        if stripped.startswith("* {"):
            scoped.append(line.replace("*", ".csb, .csb *", 1))
            continue
        if "{" in stripped and not stripped.startswith("@"):
            indent = line[: len(line) - len(line.lstrip())]
            selector, remainder = line.lstrip().split("{", 1)
            selectors = ", ".join(f".csb {part.strip()}" for part in selector.split(","))
            scoped.append(f"{indent}{selectors} {{{remainder}")
            continue
        scoped.append(line)
    return "\n".join(scoped).replace("cursor: zoom-in", "cursor: default")


def write_blogger_fragment(html: str) -> None:
    style_match = re.search(r"<style>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
    body_match = re.search(r"(<header\b.*?</footer>)", html, re.DOTALL | re.IGNORECASE)
    if not style_match or not body_match:
        raise RuntimeError("Could not locate the standalone report style or visible body")

    css = scope_css_for_blogger(style_match.group(1))
    fragment = (
        "<!-- Blogger HTML view: paste this entire file as one post. -->\n"
        f"<style>\n{css}\n</style>\n"
        f"<div class=\"csb\">\n{body_match.group(1)}\n</div>\n"
    )
    numeric_entities = re.findall(r"&#(?:\d+|x[0-9a-f]+);?", fragment, re.IGNORECASE)
    css_non_ascii_content = re.findall(
        r"content\s*:\s*['\"][^'\"]*[^\x00-\x7f][^'\"]*['\"]",
        css,
        re.IGNORECASE,
    )
    if numeric_entities or css_non_ascii_content:
        raise RuntimeError(
            f"Blogger-unsafe entities/content remain: {numeric_entities[:3]} {css_non_ascii_content[:3]}"
        )
    BLOGGER_REPORT.write_text(fragment, encoding="utf-8", newline="\n")


def main() -> None:
    html = REPORT.read_text(encoding="utf-8")
    updated, count = IMAGE_PATTERN.subn(embed, html)

    if count not in {0, 4}:
        raise RuntimeError(f"Expected 4 relative PNG references or an already embedded report; found {count}")

    embedded = updated.count('src="data:image/png;base64,')
    if embedded != 4:
        raise RuntimeError(f"Expected 4 embedded screenshots; found {embedded}")

    numeric_entities = re.findall(r"&#(?:\d+|x[0-9a-f]+);?", updated, re.IGNORECASE)
    if numeric_entities:
        raise RuntimeError(f"Numeric HTML entities remain: {numeric_entities[:5]}")

    REPORT.write_text(updated, encoding="utf-8", newline="\n")
    write_blogger_fragment(updated)
    print(
        f"embedded={embedded} bytes={REPORT.stat().st_size} "
        f"blogger_bytes={BLOGGER_REPORT.stat().st_size} numeric_entities=0"
    )


if __name__ == "__main__":
    main()
