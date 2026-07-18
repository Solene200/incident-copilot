"""防止已提交 Graph 可视化与真实源码发生理想化漂移。"""

from pathlib import Path

from incident_copilot.graph.visualization import current_mermaid, extract_documented_mermaid


def test_documented_mermaid_is_generated_from_compiled_graph() -> None:
    repository_root = Path(__file__).parents[2]

    documented = extract_documented_mermaid(repository_root / "docs" / "GRAPH_CURRENT.md")

    assert documented == current_mermaid()
