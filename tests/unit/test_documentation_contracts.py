"""Current/Experimental/Target 声明与生成文档的一致性门禁。"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CORE_DOCUMENTS = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "PRD.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "DATA_MODEL.md",
    ROOT / "docs" / "EVALUATION.md",
    ROOT / "docs" / "DEMO_GUIDE.md",
    ROOT / "docs" / "INTERVIEW_GUIDE.md",
)
MARKDOWN_LINK = re.compile(r"\[[^]]+]\(([^)]+)\)")


def test_generated_learning_guides_match_all_source_chapters() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_learning_guide.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("document", CORE_DOCUMENTS, ids=lambda path: path.name)
def test_core_document_local_links_resolve(document: Path) -> None:
    markdown = document.read_text(encoding="utf-8")
    for match in MARKDOWN_LINK.finditer(markdown):
        raw_target = match.group(1).strip("<>")
        if raw_target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_text = raw_target.partition("#")[0]
        if path_text:
            target = (document.parent / path_text).resolve()
            assert target.exists(), f"broken local link in {document}: {raw_target}"


def test_product_boundary_is_explicit_in_primary_documents() -> None:
    for relative in ("README.md", "docs/PRD.md", "docs/ARCHITECTURE.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "Current" in content
        assert "Experimental" in content
        assert "Target" in content

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "不会" in readme and "raw query" in readme
    assert "payment-only" in readme
    assert "PgVectorStore" in readme and "Experimental" in readme


def test_repository_guide_has_no_stale_phase_lock() -> None:
    guide = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "当前已完成 Phase 4" not in guide
    assert "不得开始 Phase 5" not in guide
    assert "build_learning_guide.py --check" in guide
