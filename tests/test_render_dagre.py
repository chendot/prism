import json
import re
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from prism.core.schema import PrismDoc
from prism.ontologies.loader import load_ontology
from prism.render.mermaid import DAGRE_RENDERER_PATH, DAGRE_VENDOR_PATH, MermaidRenderer


NODE_LAYOUT_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const [payloadPath, dagrePath, rendererPath] = process.argv.slice(1);
vm.runInThisContext(
  fs.readFileSync(dagrePath, "utf8") + ";globalThis.dagre=dagre;"
);
vm.runInThisContext(fs.readFileSync(rendererPath, "utf8"));
const payloads = JSON.parse(fs.readFileSync(payloadPath, "utf8"));
const layouts = payloads.map((payload) => {
  const layout = PrismDagre.layout(payload);
  layout.renderedEdges = layout.edges.map((edge) => ({
    ...edge,
    route: PrismDagre.edgeRoute(payload, edge, layout),
  }));
  return layout;
});
process.stdout.write(JSON.stringify(layouts));
"""


def _payload_from_html(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="prism-payload" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def _example_payloads() -> list[dict[str, object]]:
    renderer = MermaidRenderer()
    payloads = []
    for path in sorted(Path("examples").glob("*.yaml")):
        prism = PrismDoc.from_yaml(str(path))
        ontology = load_ontology(prism.meta.ontology)
        payloads.append(_payload_from_html(renderer.render(prism, ontology)))
    return payloads


def _run_layouts(
    payloads: list[dict[str, object]], tmp_path: Path
) -> list[dict[str, object]]:
    if shutil.which("node") is None:
        pytest.skip("Node.js is required for dagre layout smoke tests")
    payload_path = tmp_path / "dagre-payloads.json"
    payload_path.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            "node",
            "-e",
            NODE_LAYOUT_SCRIPT,
            str(payload_path),
            str(DAGRE_VENDOR_PATH),
            str(DAGRE_RENDERER_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _overlaps(first: dict[str, object], second: dict[str, object]) -> bool:
    return not (
        float(first["x"]) + float(first["width"]) / 2
        <= float(second["x"]) - float(second["width"]) / 2
        or float(second["x"]) + float(second["width"]) / 2
        <= float(first["x"]) - float(first["width"]) / 2
        or float(first["y"]) + float(first["height"]) / 2
        <= float(second["y"]) - float(second["height"]) / 2
        or float(second["y"]) + float(second["height"]) / 2
        <= float(first["y"]) - float(first["height"]) / 2
    )


def test_render_embeds_local_dagre_payload_and_python_layout_config() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    ontology = load_ontology(prism.meta.ontology)
    renderer = MermaidRenderer()

    html = renderer.render(prism, ontology)
    payload = _payload_from_html(html)

    assert '<script src=' not in html
    assert 'data-layout-engine="dagre"' in html
    assert "var dagre=" in html
    assert payload["dagre_version"] == "3.0.0"
    assert payload["layout"] == asdict(renderer.layout_config)
    assert payload["ontology"]["roles"] == ontology.roles
    assert payload["prism"]["meta"]["title"] == prism.meta.title


def test_dagre_layout_has_no_node_overlaps_for_all_examples(tmp_path: Path) -> None:
    payloads = _example_payloads()
    layouts = _run_layouts(payloads, tmp_path)

    assert len(layouts) == len(payloads)
    for payload, layout in zip(payloads, layouts):
        title = payload["prism"]["meta"]["title"]
        nodes = layout["nodes"]
        assert len(nodes) == len(payload["prism"]["nodes"])
        for index, first in enumerate(nodes):
            assert float(first["x"]) - float(first["width"]) / 2 >= 0, title
            assert float(first["y"]) - float(first["height"]) / 2 >= 0, title
            assert float(first["x"]) + float(first["width"]) / 2 <= float(layout["width"]), title
            assert float(first["y"]) + float(first["height"]) / 2 <= float(layout["height"]), title
            for second in nodes[index + 1 :]:
                assert not _overlaps(first, second), (
                    f"{title}: {first['id']} overlaps {second['id']}"
                )


def test_parallel_lanes_use_compound_parents_and_declared_column_order(
    tmp_path: Path,
) -> None:
    payloads = [
        payload
        for payload in _example_payloads()
        if payload["prism"]["render"].get("template") == "parallel_lanes"
    ]
    layouts = _run_layouts(payloads, tmp_path)

    assert payloads
    for payload, layout in zip(payloads, layouts):
        shared = {layout["shared"]["entry"], layout["shared"]["convergence"]}
        ordered_lanes = sorted(
            payload["prism"]["render"]["lanes"],
            key=lambda lane: (lane["order"], lane["id"]),
        )
        cluster_x = {cluster["id"]: float(cluster["x"]) for cluster in layout["clusters"]}
        assert [cluster_x[lane["id"]] for lane in ordered_lanes] == sorted(
            cluster_x.values()
        )
        for lane in ordered_lanes:
            lane_nodes = [
                node
                for node in layout["nodes"]
                if node.get("lane") == lane["id"] and node["id"] not in shared
            ]
            assert lane_nodes
            assert all(
                node["parent"] == f"__lane__{lane['id']}" for node in lane_nodes
            )
            assert max(float(node["x"]) for node in lane_nodes) - min(
                float(node["x"]) for node in lane_nodes
            ) < 1


def test_dagre_edges_are_drawn_as_orthogonal_polylines(tmp_path: Path) -> None:
    payloads = _example_payloads()
    layouts = _run_layouts(payloads, tmp_path)

    for payload, layout in zip(payloads, layouts):
        title = payload["prism"]["meta"]["title"]
        for edge in layout["renderedEdges"]:
            route = edge["route"]
            if route["curved"]:
                assert payload["prism"]["render"].get("template") == "parallel_lanes"
                assert " C " in route["path"]
                continue
            for start, end in zip(route["points"], route["points"][1:]):
                assert (
                    abs(float(start["x"]) - float(end["x"])) < 1e-6
                    or abs(float(start["y"]) - float(end["y"])) < 1e-6
                ), f"{title}: {edge['from']}->{edge['to']} is diagonal"


def test_parallel_lanes_keep_all_connections_and_curve_fanout_convergence(
    tmp_path: Path,
) -> None:
    payloads = [
        payload
        for payload in _example_payloads()
        if payload["prism"]["render"].get("template") == "parallel_lanes"
    ]
    layouts = _run_layouts(payloads, tmp_path)

    for payload, layout in zip(payloads, layouts):
        assert len(layout["renderedEdges"]) == len(payload["prism"]["edges"])
        curved_edges = [edge for edge in layout["renderedEdges"] if edge["route"]["curved"]]
        assert len(curved_edges) >= 2
        assert all(" C " in edge["route"]["path"] for edge in curved_edges)
