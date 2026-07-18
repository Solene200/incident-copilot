"""把分章中文教学文档合并为一份便于连续阅读的大文档。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_DIR = ROOT / "docs" / "learning"
OUTPUT_PATH = LEARNING_DIR / "INCIDENT_COPILOT_LEARNING_GUIDE.md"

CHAPTER_ICONS = {
    "learning-home": "🏠",
    "chapter-00": "🧭",
    "chapter-01": "🚨",
    "chapter-02": "🗂️",
    "chapter-03": "🔄",
    "chapter-04": "🧠",
    "chapter-05": "🕸️",
    "chapter-06": "🔌",
    "chapter-07": "🔎",
    "chapter-08": "🧪",
    "chapter-09": "⚡",
    "chapter-10": "⏸️",
    "chapter-11": "📊",
    "chapter-12": "🚀",
    "chapter-13": "💬",
    "chapter-14": "📖",
    "core-reading-index": "🧩",
}

TOC_GROUPS = (
    ("🧭 导学与项目主线", {"learning-home", *(f"chapter-{index:02d}" for index in range(4))}),
    ("🧠 核心调查机制", {f"chapter-{index:02d}" for index in range(4, 9)}),
    ("⚙️ 服务化、评估与实践", {f"chapter-{index:02d}" for index in range(9, 15)}),
    ("🧩 核心源码精读", {"core-reading-index"}),
)


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


def _shift_headings(markdown: str, *, icon: str) -> str:
    """把分章标题整体下移一级, 并为章节主标题添加视觉标识。"""
    shifted: list[str] = []
    in_fence = False
    decorated_title = False
    for line in markdown.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            shifted.append(line)
            continue
        if not in_fence and not decorated_title and line.startswith("# "):
            line = f"# {icon} {line.removeprefix('# ')}"
            decorated_title = True
        if not in_fence and re.match(r"^#{1,5} ", line):
            line = f"#{line}"
        if not in_fence and line.startswith("下一步: "):
            line = f"> **➡️ 下一步:** {line.removeprefix('下一步: ')}"
        if not in_fence and line.startswith("完成标志: "):
            line = f"> **✅ 完成标志:** {line.removeprefix('完成标志: ')}"
        shifted.append(line)
    return "\n".join(shifted).strip()


def _toc_group(anchor: str) -> str:
    """返回章节所属的目录分组, 源码精读文件统一归入最后一组。"""
    if anchor.startswith("walkthrough-"):
        return "🧩 核心源码精读"
    for title, anchors in TOC_GROUPS:
        if anchor in anchors:
            return title
    raise ValueError(f"learning chapter has no table-of-contents group: {anchor}")


def _chapter_icon(anchor: str) -> str:
    """为章节返回稳定图标, 源码精读使用统一的代码图标。"""
    if anchor.startswith("walkthrough-"):
        return "👨‍💻"
    return CHAPTER_ICONS[anchor]


def build_learning_guide() -> str:
    """按既定学习顺序生成完整教学文档。"""
    anchors = {chapter.path.resolve(): chapter.anchor for chapter in CHAPTERS}
    source_documents = [chapter.path.read_text(encoding="utf-8") for chapter in CHAPTERS]
    titles = [_title(markdown) for markdown in source_documents]

    lines = [
        '<a id="top"></a>',
        "",
        '<div align="center">',
        "",
        "# 🚨 IncidentCopilot 中文教学版",
        "",
        "<p><strong>从一次故障告警, 到一份可恢复、可审计、带引用的智能诊断报告</strong></p>",
        "",
        '<p><span style="color:#2563EB"><strong>LangGraph 工作流</strong></span> · '
        '<span style="color:#059669"><strong>多源可观测性</strong></span> · '
        '<span style="color:#7C3AED"><strong>混合 RAG</strong></span> · '
        '<span style="color:#DC2626"><strong>人工审核</strong></span></p>',
        "",
        "<p><strong>适合:</strong> AI 应用开发岗位面试 · 作品集展示 · LangGraph 工程化学习</p>",
        "",
        "</div>",
        "",
        "> [!TIP]",
        "> 第一次阅读建议从 **🧭 学习路线** 开始; 准备面试时可直接进入 **🧩 核心源码精读**。",
        "",
        "> [!NOTE]",
        "> 本文档由分章教学文件自动合并生成。需要维护内容时请修改分章文件, 然后运行",
        "> `uv run python scripts/build_learning_guide.py` 重新生成。",
        "",
        "## 📚 目录",
        "",
    ]
    current_group = ""
    for chapter, title in zip(CHAPTERS, titles, strict=True):
        group = _toc_group(chapter.anchor)
        if group != current_group:
            lines.extend(("", f"### {group}", ""))
            current_group = group
        lines.append(f"- {_chapter_icon(chapter.anchor)} [{title}](#{chapter.anchor})")

    for index, (chapter, markdown) in enumerate(zip(CHAPTERS, source_documents, strict=True)):
        rewritten = _rewrite_links(markdown, chapter.path, anchors)
        icon = _chapter_icon(chapter.anchor)
        return_to_top = (
            () if index == 0 else ('<div align="right"><a href="#top">⬆️ 返回顶部</a></div>', "")
        )
        lines.extend(
            (
                "",
                *return_to_top,
                "---",
                "",
                f'<a id="{chapter.anchor}"></a>',
                "",
                _shift_headings(rewritten, icon=icon),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """生成合并后的 Markdown 文件。"""
    OUTPUT_PATH.write_text(build_learning_guide(), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT_PATH.relative_to(ROOT)} from {len(CHAPTERS)} chapters")


if __name__ == "__main__":
    main()
