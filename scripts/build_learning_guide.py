"""把分章中文教学文档合并为一份便于连续阅读的大文档。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_DIR = ROOT / "docs" / "learning"
OUTPUT_PATH = LEARNING_DIR / "INCIDENT_COPILOT_LEARNING_GUIDE.md"


@dataclass(frozen=True, slots=True)
class Chapter:
    """描述一个待合并章节及其稳定锚点。"""

    path: Path
    anchor: str


CHAPTERS = (
    Chapter(LEARNING_DIR / "README.md", "learning-home"),
    *(
        Chapter(path, f"chapter-{path.name[:2]}")
        for path in sorted(LEARNING_DIR.glob("[0-1][0-9]-*.md"))
    ),
    Chapter(LEARNING_DIR / "core-reading-index.md", "core-reading-index"),
    *(
        Chapter(path, f"walkthrough-{path.name[:2]}")
        for path in sorted((LEARNING_DIR / "code-walkthrough").glob("[0-1][0-9]-*.md"))
    ),
)

MARKDOWN_LINK = re.compile(r"\[([^\]]+)]\(([^)]+)\)")


def _title(markdown: str) -> str:
    """读取文档的第一个一级标题。"""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    raise ValueError("learning chapter is missing an H1 heading")


def _rewrite_links(markdown: str, source: Path, anchors: dict[Path, str]) -> str:
    """把分章链接改为内部锚点,并修正合并后源码链接的相对路径。"""

    def replace(match: re.Match[str]) -> str:
        label, raw_target = match.groups()
        if raw_target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)

        target_text = raw_target.strip("<>")
        path_text, separator, fragment = target_text.partition("#")
        if not path_text:
            return match.group(0)

        target = (source.parent / path_text).resolve()
        if target in anchors:
            return f"[{label}](#{anchors[target]})"

        relative = Path(os.path.relpath(target, OUTPUT_PATH.parent)).as_posix()
        suffix = f"#{fragment}" if separator else ""
        return f"[{label}]({relative}{suffix})"

    return MARKDOWN_LINK.sub(replace, markdown)


def _shift_headings(markdown: str) -> str:
    """把分章标题整体下移一级,同时跳过代码围栏中的内容。"""
    shifted: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            shifted.append(line)
            continue
        if not in_fence and re.match(r"^#{1,5} ", line):
            line = f"#{line}"
        shifted.append(line)
    return "\n".join(shifted).strip()


def build_learning_guide() -> str:
    """按既定学习顺序生成完整教学文档。"""
    anchors = {chapter.path.resolve(): chapter.anchor for chapter in CHAPTERS}
    source_documents = [chapter.path.read_text(encoding="utf-8") for chapter in CHAPTERS]
    titles = [_title(markdown) for markdown in source_documents]

    lines = [
        "# IncidentCopilot 中文教学版",
        "",
        "> 本文档由分章教学文件自动合并生成。需要维护内容时请修改分章文件,然后运行",
        "> `uv run python scripts/build_learning_guide.py` 重新生成。",
        "",
        "## 目录",
        "",
    ]
    for chapter, title in zip(CHAPTERS, titles, strict=True):
        lines.append(f"- [{title}](#{chapter.anchor})")

    for chapter, markdown in zip(CHAPTERS, source_documents, strict=True):
        rewritten = _rewrite_links(markdown, chapter.path, anchors)
        lines.extend(
            (
                "",
                "---",
                "",
                f'<a id="{chapter.anchor}"></a>',
                "",
                _shift_headings(rewritten),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """生成合并后的 Markdown 文件。"""
    OUTPUT_PATH.write_text(build_learning_guide(), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT_PATH.relative_to(ROOT)} from {len(CHAPTERS)} chapters")


if __name__ == "__main__":
    main()
