"""检查仓库内自然语言注释和 docstring 是否使用中文。"""

from __future__ import annotations

import ast
import io
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SUFFIXES = {".yaml", ".yml", ".toml", ".ini", ".cfg", ".ps1", ".sh"}
DIRECTIVE_MARKERS = ("noqa", "type: ignore", "pragma:", "#!", "coding:", "# syntax=")


def _tracked_files(pattern: str | None = None) -> tuple[Path, ...]:
    """返回 Git 已跟踪文件,避免扫描虚拟环境和生成缓存。"""
    command = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    if pattern is not None:
        command.append(pattern)
    output = subprocess.check_output(command, cwd=ROOT, text=True, encoding="utf-8")
    return tuple(ROOT / item for item in output.splitlines())


def _contains_english_without_chinese(value: str) -> bool:
    """判断文本是否包含英文字符但完全没有中文字符。"""
    has_english = any(character.isascii() and character.isalpha() for character in value)
    has_chinese = any("\u4e00" <= character <= "\u9fff" for character in value)
    return has_english and not has_chinese


def _python_problems(path: Path) -> list[str]:
    """检查一个 Python 文件的 docstring 和 Token 级行注释。"""
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    problems: list[str] = []
    node_types = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, node_types):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring is None:
            continue
        for line in docstring.splitlines():
            if line.strip() and _contains_english_without_chinese(line):
                relative = path.relative_to(ROOT)
                problems.append(f"{relative}:{getattr(node, 'lineno', 1)}:英文 docstring")
                break

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if any(marker in token.string for marker in DIRECTIVE_MARKERS):
            continue
        if _contains_english_without_chinese(token.string):
            relative = path.relative_to(ROOT)
            problems.append(f"{relative}:{token.start[0]}:英文行注释")
    return problems


def _config_problems(path: Path) -> list[str]:
    """检查常见配置和容器文件中的整行注释。"""
    problems: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if any(marker in stripped for marker in DIRECTIVE_MARKERS):
            continue
        if _contains_english_without_chinese(stripped):
            relative = path.relative_to(ROOT)
            problems.append(f"{relative}:{line_number}:英文配置注释")
    return problems


def main() -> None:
    """扫描全部已跟踪代码文件,发现英文注释时返回非零退出码。"""
    problems: list[str] = []
    for path in _tracked_files("*.py"):
        problems.extend(_python_problems(path))
    for path in _tracked_files():
        if path.suffix.lower() in CONFIG_SUFFIXES or path.name == "Dockerfile":
            problems.extend(_config_problems(path))

    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    print("中文注释检查通过")


if __name__ == "__main__":
    main()
