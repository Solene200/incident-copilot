"""把分章中文教学文档合并为一份便于连续阅读的大文档。"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_DIR = ROOT / "docs" / "learning"
OUTPUT_PATH = LEARNING_DIR / "INCIDENT_COPILOT_LEARNING_GUIDE.md"
SOURCE_GUIDE_PATH = LEARNING_DIR / "INCIDENT_COPILOT_SOURCE_CODE_GUIDE.md"
SOURCE_ROOT = ROOT / "src" / "incident_copilot"

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
    "source-foundations": "🧱",
}

TOC_GROUPS = (
    ("🧭 导学与项目主线", {"learning-home", *(f"chapter-{index:02d}" for index in range(4))}),
    ("🧠 核心调查机制", {f"chapter-{index:02d}" for index in range(4, 9)}),
    ("⚙️ 服务化、评估与实践", {f"chapter-{index:02d}" for index in range(9, 15)}),
    ("🧩 全部源码精读", {"core-reading-index"}),
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
        for path in sorted((LEARNING_DIR / "code-walkthrough").glob("[0-9][0-9]-*.md"))
    ),
)

SOURCE_WALKTHROUGH_ORDER = (
    "15-domain-models.md",
    "14-core-infrastructure.md",
    "17-graph-support.md",
    "20-tool-contracts-builtin.md",
    "19-rag-schemas-vector-store.md",
    "16-investigation-storage-fixtures.md",
    "22-evaluation-support.md",
    "18-rag-ingestion.md",
    "11-hybrid-retrieval.md",
    "21-tool-providers.md",
    "10-tool-registry.md",
    "09-model-provider.md",
    "05-graph-state.md",
    "07-graph-nodes.md",
    "08-graph-routing.md",
    "06-graph-builder.md",
    "04-checkpoint.md",
    "03-investigation-service.md",
    "02-investigation-api.md",
    "01-main.md",
    "13-application-api-support.md",
    "12-evaluation-runner.md",
)

SOURCE_CHAPTERS = (
    Chapter(LEARNING_DIR / "source-reading-foundations.md", "source-foundations"),
    Chapter(LEARNING_DIR / "core-reading-index.md", "core-reading-index"),
    *(
        Chapter(LEARNING_DIR / "code-walkthrough" / filename, f"walkthrough-{filename[:2]}")
        for filename in SOURCE_WALKTHROUGH_ORDER
    ),
)

SOURCE_TOC_GROUPS = (
    ("🧱 阅读前的基础定义", {"source-foundations", "core-reading-index"}),
    (
        "📐 类型、契约与数据结构",
        {f"walkthrough-{index:02d}" for index in (14, 15, 16, 17, 19, 20, 22)},
    ),
    ("🔌 数据获取与检索", {f"walkthrough-{index:02d}" for index in (10, 11, 18, 21)}),
    ("🕸️ Graph 控制流", {f"walkthrough-{index:02d}" for index in (5, 6, 7, 8, 9)}),
    ("⚡ 任务、API 与启动", {f"walkthrough-{index:02d}" for index in (1, 2, 3, 4, 13)}),
    ("📊 离线评估编排", {"walkthrough-12"}),
)

MARKDOWN_LINK = re.compile(r"\[([^\]]+)]\(([^)]+)\)")


def _title(markdown: str) -> str:
    """读取文档的第一个一级标题。"""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    raise ValueError("learning chapter is missing an H1 heading")


def _rewrite_links(
    markdown: str,
    source: Path,
    anchors: dict[Path, str],
    *,
    output_path: Path = OUTPUT_PATH,
) -> str:
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

        relative = Path(os.path.relpath(target, output_path.parent)).as_posix()
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
        return "🧩 全部源码精读"
    for title, anchors in TOC_GROUPS:
        if anchor in anchors:
            return title
    raise ValueError(f"learning chapter has no table-of-contents group: {anchor}")


def _chapter_icon(anchor: str) -> str:
    """为章节返回稳定图标, 源码精读使用统一的代码图标。"""
    if anchor.startswith("walkthrough-"):
        return "👨‍💻"
    return CHAPTER_ICONS[anchor]


def _source_toc_group(anchor: str) -> str:
    """按照定义优先的源码阅读顺序返回目录分组。"""
    for title, anchors in SOURCE_TOC_GROUPS:
        if anchor in anchors:
            return title
    raise ValueError(f"source chapter has no table-of-contents group: {anchor}")


def _source_chapter_icon(anchor: str) -> str:
    """让源码解析章节的图标表达当前阅读阶段。"""
    return _source_toc_group(anchor).split(maxsplit=1)[0]


def _strip_original_navigation(markdown: str) -> str:
    """删除分章原编号顺序的尾部导航, 由源码导读重新生成。"""
    lines = markdown.rstrip().splitlines()
    if lines and lines[-1].startswith(("下一篇", "返回[", "下一步")):
        lines.pop()
    return "\n".join(lines).strip()


def _validate_source_coverage() -> None:
    """确保每个应用源码文件都能从至少一份精读文档直接打开。"""
    expected = {path.resolve() for path in SOURCE_ROOT.rglob("*.py")}
    linked: set[Path] = set()
    walkthrough_dir = LEARNING_DIR / "code-walkthrough"
    for document_path in sorted(walkthrough_dir.glob("[0-9][0-9]-*.md")):
        markdown = document_path.read_text(encoding="utf-8")
        for _, raw_target in MARKDOWN_LINK.findall(markdown):
            path_text = raw_target.strip("<>").partition("#")[0]
            if not path_text or raw_target.startswith(("http://", "https://", "mailto:")):
                continue
            target = (document_path.parent / path_text).resolve()
            if target.suffix == ".py" and target.is_relative_to(SOURCE_ROOT.resolve()):
                linked.add(target)

    missing = sorted(expected - linked)
    stale = sorted(linked - expected)
    if missing or stale:
        details = [
            *(f"缺少源码精读链接: {path.relative_to(ROOT).as_posix()}" for path in missing),
            *(f"源码精读链接已失效: {path.relative_to(ROOT).as_posix()}" for path in stale),
        ]
        raise ValueError("源码精读覆盖检查失败\n" + "\n".join(details))


def build_learning_guide() -> str:
    """按既定学习顺序生成完整教学文档。"""
    _validate_source_coverage()
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
        "> 英文术语不熟悉时先看 **[📘 常见英文速查](#english-terms)**; 第一次系统阅读建议从 "
        "**🧭 学习路线** 开始。",
        "> 想直接对照源码学习, 可以进入 **[🧩 完整源码阅读索引](#core-reading-index)**。",
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


def build_source_code_guide() -> str:
    """按先定义、再数据流、最后业务控制流的顺序生成源码解析文档。"""
    _validate_source_coverage()
    anchors = {chapter.path.resolve(): chapter.anchor for chapter in SOURCE_CHAPTERS}
    source_documents = [chapter.path.read_text(encoding="utf-8") for chapter in SOURCE_CHAPTERS]
    titles = [_title(markdown) for markdown in source_documents]

    lines = [
        '<a id="source-top"></a>',
        "",
        '<div align="center">',
        "",
        "# 🧩 IncidentCopilot 源码解析版",
        "",
        "<p><strong>先认识常量、类型和数据关系, 再进入真实业务控制流</strong></p>",
        "",
        '<p><span style="color:#2563EB"><strong>定义优先</strong></span> · '
        '<span style="color:#059669"><strong>依赖顺序</strong></span> · '
        '<span style="color:#7C3AED"><strong>逐段对照源码</strong></span></p>',
        "",
        "</div>",
        "",
        "> [!TIP]",
        "> 第一次阅读先完成 **🧱 源码阅读基础**, 不要直接跳到 Graph Node。",
        "> 已经熟悉定义时, 可以使用 **🧩 完整源码阅读索引** 按问题跳转。",
        "",
        "> [!NOTE]",
        "> 本文档复用仓库中的真实源码精读并按依赖重新排序。维护分章后运行",
        "> `uv run python scripts/build_learning_guide.py` 可同时重新生成两份大文档。",
        "",
        "## 📚 定义优先阅读目录",
        "",
    ]
    current_group = ""
    for chapter, title in zip(SOURCE_CHAPTERS, titles, strict=True):
        group = _source_toc_group(chapter.anchor)
        if group != current_group:
            lines.extend(("", f"### {group}", ""))
            current_group = group
        lines.append(f"- {_source_chapter_icon(chapter.anchor)} [{title}](#{chapter.anchor})")

    for index, (chapter, markdown, _title_text) in enumerate(
        zip(SOURCE_CHAPTERS, source_documents, titles, strict=True)
    ):
        prepared = (
            _strip_original_navigation(markdown)
            if chapter.anchor.startswith("walkthrough-")
            else markdown
        )
        rewritten = _rewrite_links(
            prepared,
            chapter.path,
            anchors,
            output_path=SOURCE_GUIDE_PATH,
        )
        icon = _source_chapter_icon(chapter.anchor)
        navigation = ""
        if index + 1 < len(SOURCE_CHAPTERS):
            next_chapter = SOURCE_CHAPTERS[index + 1]
            next_title = titles[index + 1]
            navigation = f"> **➡️ 按本导读顺序, 下一篇:** [{next_title}](#{next_chapter.anchor})"
        else:
            navigation = "> **✅ 源码导读完成:** 接下来可运行测试并在 IDE 中设置断点。"
        lines.extend(
            (
                "",
                '<div align="right"><a href="#source-top">⬆️ 返回源码目录</a></div>',
                "",
                "---",
                "",
                f'<a id="{chapter.anchor}"></a>',
                "",
                _shift_headings(rewritten, icon=icon),
                "",
                navigation,
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def check_generated_guides() -> None:
    """验证跟踪的聚合指南与当前分章及源码覆盖完全一致。"""
    expected = {
        OUTPUT_PATH: build_learning_guide(),
        SOURCE_GUIDE_PATH: build_source_code_guide(),
    }
    stale = [
        path.relative_to(ROOT).as_posix()
        for path, content in expected.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if stale:
        raise ValueError("Learning Guide 生成产物已过期\n" + "\n".join(stale))


def main() -> None:
    """生成聚合指南,或在不写文件的情况下检查跟踪产物。"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate source coverage and tracked generated guides without writing files.",
    )
    arguments = parser.parse_args()
    if arguments.check:
        check_generated_guides()
        print("Learning Guide source coverage and generated files are current")
        return
    OUTPUT_PATH.write_text(build_learning_guide(), encoding="utf-8", newline="\n")
    SOURCE_GUIDE_PATH.write_text(build_source_code_guide(), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT_PATH.relative_to(ROOT)} from {len(CHAPTERS)} chapters")
    print(f"Generated {SOURCE_GUIDE_PATH.relative_to(ROOT)} from {len(SOURCE_CHAPTERS)} chapters")


if __name__ == "__main__":
    main()
