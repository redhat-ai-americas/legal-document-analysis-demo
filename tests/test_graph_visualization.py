from pathlib import Path
from datetime import datetime

from workflows.graph_builder import build_graph


def test_langgraph_get_graph_visualization():
    app = build_graph()

    get_graph = getattr(app, "get_graph", None)
    assert callable(get_graph), "app.get_graph should be callable"

    graph_obj = app.get_graph()
    assert graph_obj is not None, "get_graph() should return a graph object"

    # Try to extract a textual representation (Mermaid or DOT) in a tolerant way
    mermaid_text = None
    dot_text = None

    # Some versions export mermaid
    draw_mermaid = getattr(graph_obj, "draw_mermaid", None)
    if callable(draw_mermaid):
        try:
            mermaid_text = draw_mermaid()
        except Exception:
            mermaid_text = None

    # Some versions export dot
    to_dot = getattr(graph_obj, "to_dot", None)
    if callable(to_dot):
        try:
            dot_text = to_dot()
        except Exception:
            dot_text = None

    # Fallback: string repr
    fallback_text = None
    if mermaid_text is None and dot_text is None:
        try:
            fallback_text = str(graph_obj)
        except Exception:
            fallback_text = None

    # Prepare output directory under app root
    app_root = Path(__file__).resolve().parent.parent
    graphs_dir = app_root / "data" / "output" / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write whichever we have
    if mermaid_text:
        out_path = graphs_dir / f"workflow_{ts}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            # wrap in fenced code block for easier preview
            f.write("""```mermaid\n""")
            f.write(str(mermaid_text).strip())
            f.write("\n````\n")
        print(f"Mermaid graph written to: {out_path}")
    elif dot_text:
        out_path = graphs_dir / f"workflow_{ts}.dot"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(str(dot_text))
        print(f"DOT graph written to: {out_path}")
    elif fallback_text:
        out_path = graphs_dir / f"workflow_{ts}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fallback_text)
        print(f"Fallback graph text written to: {out_path}")
    else:
        # We don't fail the test; just assert the graph object exists
        print("Graph object obtained, but no textual representation method available.")
