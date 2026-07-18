"""Guard the committed graph visualization against idealized documentation drift."""

from pathlib import Path

from incident_copilot.graph.visualization import current_mermaid, extract_documented_mermaid


def test_documented_mermaid_is_generated_from_compiled_graph() -> None:
    repository_root = Path(__file__).parents[2]

    documented = extract_documented_mermaid(repository_root / "docs" / "GRAPH_CURRENT.md")

    assert documented == current_mermaid()
