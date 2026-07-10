(function (root) {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  function createSvg(tag, attrs, text) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") {
        element.setAttribute(key, String(value));
      }
    });
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function edgeRepresentedByLoop(edge, prism) {
    if (edge.type !== "feedback" && edge.direction !== "backward") return false;
    return prism.loops.some((loop) => {
      if (loop.nodes.length < 2) return false;
      return loop.nodes.some((source, index) => {
        const target = loop.nodes[(index + 1) % loop.nodes.length];
        return new Set([source, target]).size === new Set([edge.from, edge.to]).size &&
          [source, target].every((nodeId) => [edge.from, edge.to].includes(nodeId));
      });
    });
  }

  function visibleEdges(prism) {
    return prism.edges.filter(
      (edge) => !(prism.render.show_loops && edgeRepresentedByLoop(edge, prism))
    );
  }

  function sharedLaneNodes(prism, laneIds) {
    const laneByNode = Object.fromEntries(prism.nodes.map((node) => [node.id, node.lane]));
    let entry = null;
    let convergence = null;
    prism.nodes.forEach((node) => {
      const targetLanes = new Set(
        prism.edges
          .filter((edge) => edge.from === node.id && edge.to !== node.id)
          .map((edge) => laneByNode[edge.to])
          .filter(Boolean)
      );
      if (laneIds.every((laneId) => targetLanes.has(laneId))) entry = node.id;

      const sourceLanes = new Set(
        prism.edges
          .filter((edge) => edge.to === node.id && laneByNode[edge.from] !== node.lane)
          .map((edge) => laneByNode[edge.from])
          .filter(Boolean)
      );
      if (laneIds.filter((laneId) => sourceLanes.has(laneId)).length >= 2) {
        convergence = node.id;
      }
    });
    return { entry, convergence };
  }

  function roleVisual(payload, node) {
    return payload.ontology.roles[node.role]?.visual || {};
  }

  function nodeDimensions(payload, node, parallelLaneCount) {
    const config = payload.layout;
    const visual = roleVisual(payload, node);
    const scale = Number(visual.scale || 1);
    const baseWidth = parallelLaneCount
      ? ((config.canvas_width - 2 * config.lane_padding) / parallelLaneCount) *
        config.node_width_ratio
      : config.node_width;
    return {
      width: baseWidth * scale,
      height: config.node_height * scale,
    };
  }

  function estimateTextWidth(text, fontSize) {
    let units = 0;
    for (const char of text || "") units += char.codePointAt(0) > 255 ? 1 : 0.58;
    return units * fontSize + 8;
  }

  function isParallel(payload) {
    return payload.prism.render.template === "parallel_lanes";
  }

  function buildGraph(payload) {
    const prism = payload.prism;
    const config = payload.layout;
    const parallel = isParallel(payload);
    const laneDefs = parallel
      ? [...(prism.render.lanes || [])].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id))
      : [];
    const laneIds = laneDefs.map((lane) => lane.id);
    const shared = parallel ? sharedLaneNodes(prism, laneIds) : { entry: null, convergence: null };
    const graph = new root.dagre.graphlib.Graph({ compound: parallel, multigraph: true });
    graph.setGraph({
      rankdir: parallel ? "TB" : prism.diagram.direction,
      ranker: "network-simplex",
      ranksep: config.node_gap,
      nodesep: config.node_column_gap,
      edgesep: config.edge_track_gap,
      marginx: config.node_route_clearance,
      marginy: config.top_margin,
    });
    graph.setDefaultEdgeLabel(() => ({}));

    if (parallel) {
      laneDefs.forEach((lane) => {
        graph.setNode(`__lane__${lane.id}`, {
          cluster: true,
          laneId: lane.id,
          title: lane.title,
          width: config.node_width,
          height: config.node_height,
        });
      });
    }

    prism.nodes.forEach((node) => {
      const dimensions = nodeDimensions(payload, node, laneIds.length);
      graph.setNode(node.id, {
        ...dimensions,
        nodeId: node.id,
      });
      if (
        parallel &&
        node.lane &&
        laneIds.includes(node.lane) &&
        node.id !== shared.entry &&
        node.id !== shared.convergence
      ) {
        graph.setParent(node.id, `__lane__${node.lane}`);
      }
    });

    const renderedEdges = visibleEdges(prism);
    const deferredEdges = [];
    renderedEdges.forEach((edge, index) => {
      if (edge.type === "feedback" || edge.direction === "backward") {
        deferredEdges.push({ edge, edgeIndex: index });
        return;
      }
      const source = prism.nodes.find((node) => node.id === edge.from);
      const target = prism.nodes.find((node) => node.id === edge.to);
      const layerDistance =
        source?.layer !== null && source?.layer !== undefined &&
        target?.layer !== null && target?.layer !== undefined
          ? Math.max(1, Math.abs(target.layer - source.layer))
          : 1;
      graph.setEdge(
        edge.from,
        edge.to,
        {
          edgeIndex: index,
          hidden: false,
          width: edge.label ? estimateTextWidth(edge.label, config.edge_label_font_size) : 0,
          height: edge.label ? config.edge_label_font_size + 6 : 0,
          labelpos: "c",
          minlen: layerDistance,
          weight: edge.type === "feedback" ? 0.25 : 1,
        },
        `edge-${index}`
      );
    });

    if (parallel) {
      laneDefs.forEach((lane) => {
        const laneNodes = prism.nodes
          .filter(
            (node) =>
              node.lane === lane.id &&
              node.id !== shared.entry &&
              node.id !== shared.convergence
          )
          .sort((left, right) => {
            const leftLayer = left.layer ?? Number.MAX_SAFE_INTEGER;
            const rightLayer = right.layer ?? Number.MAX_SAFE_INTEGER;
            return leftLayer - rightLayer ||
              prism.nodes.indexOf(left) - prism.nodes.indexOf(right);
          });
        laneNodes.slice(0, -1).forEach((node, index) => {
          graph.setEdge(
            node.id,
            laneNodes[index + 1].id,
            { hidden: true, minlen: 1, weight: 100 },
            `lane-${lane.id}-${index}`
          );
        });
      });
    }

    return { graph, renderedEdges, deferredEdges, laneDefs, shared };
  }

  function layout(payload) {
    if (!root.dagre) throw new Error("Bundled dagre runtime is unavailable");
    const { graph, renderedEdges, deferredEdges, laneDefs, shared } = buildGraph(payload);
    root.dagre.layout(graph);
    const prism = payload.prism;
    const nodes = prism.nodes.map((node) => {
      const positioned = graph.node(node.id);
      return {
        ...node,
        x: positioned.x,
        y: positioned.y,
        width: positioned.width,
        height: positioned.height,
        parent: graph.parent(node.id) || null,
      };
    });
    const edges = graph.edges()
      .map((descriptor) => {
        const positioned = graph.edge(descriptor);
        if (positioned.hidden) return null;
        const edge = renderedEdges[positioned.edgeIndex];
        return {
          ...edge,
          points: positioned.points,
          x: positioned.x,
          y: positioned.y,
        };
      })
      .filter(Boolean);
    const clusters = laneDefs.map((lane) => {
      const positioned = graph.node(`__lane__${lane.id}`);
      return {
        id: lane.id,
        title: lane.title,
        order: lane.order,
        x: positioned.x,
        y: positioned.y,
        width: positioned.width,
        height: positioned.height,
      };
    });
    const normalized = isParallel(payload)
      ? normalizeParallelLaneOrder(payload, { nodes, edges, clusters, shared })
      : { nodes, edges, clusters, width: graph.graph().width };
    const deferredLayoutEdges = deferredEdges.map(({ edge }) =>
      routeDeferredEdge(edge, normalized.nodes, normalized.width, payload.layout)
    );
    const loopPanelHeight =
      prism.render.show_loops && prism.loops.length ? payload.layout.node_height + 32 : 0;
    return {
      nodes: normalized.nodes,
      edges: normalized.edges.concat(deferredLayoutEdges),
      clusters: normalized.clusters,
      shared,
      width: Math.max(payload.layout.canvas_width, normalized.width),
      height: graph.graph().height + payload.layout.bottom_margin + loopPanelHeight,
      graphHeight: graph.graph().height,
      loopPanelHeight,
      dagreVersion: root.dagre.version,
    };
  }

  function routeDeferredEdge(edge, nodes, width, config) {
    const source = nodes.find((node) => node.id === edge.from);
    const target = nodes.find((node) => node.id === edge.to);
    const routeX = width - config.edge_outer_margin;
    const start = { x: source.x + source.width / 2, y: source.y };
    const end = { x: target.x + target.width / 2, y: target.y };
    return {
      ...edge,
      deferred: true,
      points: [start, { x: routeX, y: start.y }, { x: routeX, y: end.y }, end],
      x: routeX - estimateTextWidth(edge.label || "", config.edge_label_font_size) / 2,
      y: (start.y + end.y) / 2,
    };
  }

  function normalizeParallelLaneOrder(payload, result) {
    const config = payload.layout;
    const ordered = [...result.clusters].sort(
      (left, right) => left.order - right.order || left.id.localeCompare(right.id)
    );
    const deltas = {};
    let cursor = config.lane_padding;
    ordered.forEach((cluster) => {
      const targetX = cursor + cluster.width / 2;
      const delta = targetX - cluster.x;
      cluster.x = targetX;
      payload.prism.nodes
        .filter(
          (node) =>
            node.lane === cluster.id &&
            node.id !== result.shared.entry &&
            node.id !== result.shared.convergence
        )
        .forEach((node) => { deltas[node.id] = delta; });
      cursor += cluster.width + config.node_column_gap;
    });
    const laneWidth = Math.max(config.canvas_width, cursor - config.node_column_gap + config.lane_padding);
    const laneCenter = laneWidth / 2;
    [result.shared.entry, result.shared.convergence].filter(Boolean).forEach((nodeId) => {
      const node = result.nodes.find((candidate) => candidate.id === nodeId);
      if (node) deltas[nodeId] = laneCenter - node.x;
    });
    result.nodes.forEach((node) => { node.x += deltas[node.id] || 0; });
    result.edges.forEach((edge) => {
      const source = result.nodes.find((node) => node.id === edge.from);
      const target = result.nodes.find((node) => node.id === edge.to);
      const sourceDelta = deltas[edge.from] || 0;
      const targetDelta = deltas[edge.to] || 0;
      const span = (target?.y || 0) - (source?.y || 0);
      edge.points = edge.points.map((point) => {
        const ratio = Math.abs(span) < 0.1 ? 0.5 : Math.max(0, Math.min(1, (point.y - source.y) / span));
        return { ...point, x: point.x + sourceDelta + (targetDelta - sourceDelta) * ratio };
      });
      if (Number.isFinite(edge.x)) edge.x += (sourceDelta + targetDelta) / 2;
    });
    return { ...result, width: laneWidth };
  }

  function appendDefinitions(svg, payload) {
    const theme = payload.theme;
    const config = payload.layout;
    const defs = createSvg("defs");
    const gradients = [
      ["grad_neutral", theme.surface, theme.background, 1],
      ["grad_positive", theme.accent_result, theme.accent_result, 0.82],
      ["grad_highlight", theme.accent_result, theme.accent_result, 0.82],
    ];
    gradients.forEach(([id, start, end, opacity]) => {
      const gradient = createSvg("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 });
      gradient.appendChild(createSvg("stop", { offset: "0%", "stop-color": start }));
      gradient.appendChild(
        createSvg("stop", { offset: "100%", "stop-color": end, "stop-opacity": opacity })
      );
      defs.appendChild(gradient);
    });
    [
      ["primary", theme.accent_primary],
      ["secondary", theme.accent_secondary],
    ].forEach(([kind, color]) => {
      [
        ["filled_triangle", 1],
        ["filled_triangle_large", 1.4],
        ["open_triangle", 1],
      ].forEach(([arrow, multiplier]) => {
        const size = config.arrowhead_size * multiplier;
        const marker = createSvg("marker", {
          id: `${arrow}_${kind}`,
          markerWidth: size,
          markerHeight: size,
          refX: size,
          refY: size / 2,
          orient: "auto",
          markerUnits: "strokeWidth",
        });
        const path = createSvg("path", {
          d: `M 0 0 L ${size} ${size / 2} L 0 ${size}${arrow === "open_triangle" ? "" : " z"}`,
          fill: arrow === "open_triangle" ? "none" : color,
          stroke: arrow === "open_triangle" ? color : "none",
        });
        marker.appendChild(path);
        defs.appendChild(marker);
      });
    });
    const glow = createSvg("filter", { id: "glow", x: "-20%", y: "-20%", width: "140%", height: "140%" });
    glow.innerHTML = `<feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />` +
      `<feFlood flood-color="${theme.accent_result}" flood-opacity="0.6" result="glow-color" />` +
      `<feComposite in="glow-color" in2="blur" operator="in" result="glow" />` +
      `<feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>`;
    defs.appendChild(glow);
    svg.appendChild(defs);
  }

  function statusStyle(node, theme) {
    if (node.status === "positive") {
      return { fill: "url(#grad_positive)", border: theme.accent_result, text: theme.background };
    }
    if (node.status === "highlight") {
      return { fill: "url(#grad_highlight)", border: theme.accent_result, text: theme.background };
    }
    if (node.status === "negative") {
      return { fill: theme.surface, border: theme.accent_risk, text: theme.text_primary };
    }
    return { fill: "url(#grad_neutral)", border: theme.accent_primary, text: theme.text_primary };
  }

  function truncate(text, maxChars) {
    if (!text || text.length <= maxChars) return text || "";
    return `${text.slice(0, Math.max(1, maxChars - 3)).trim()}...`;
  }

  function renderNode(group, payload, node) {
    const config = payload.layout;
    const theme = payload.theme;
    const visual = roleVisual(payload, node);
    const style = statusStyle(node, theme);
    const x = node.x - node.width / 2;
    const y = node.y - node.height / 2;
    const radius = visual.shape === "round" ? Math.max(16, Number(visual.radius || 8)) : Number(visual.radius || 8);
    const dash = node.role === "risk" ? visual.border_dash : null;
    const outer = createSvg("rect", {
      class: "node-shape node-shape-outer",
      x, y, width: node.width, height: node.height, rx: radius,
      fill: style.fill,
      stroke: style.border,
      "stroke-width": visual.border_width || 1,
      "stroke-dasharray": dash,
      filter: node.status === "highlight" ? "url(#glow)" : null,
    });
    group.appendChild(outer);
    if (visual.shape === "double_border") {
      group.appendChild(createSvg("rect", {
        class: "node-shape node-shape-inner",
        x: x + 3, y: y + 3, width: node.width - 6, height: node.height - 6,
        rx: Math.max(0, radius - 3), fill: "none", stroke: style.border,
        "stroke-width": Math.max(0.5, Number(visual.border_width || 1) - 0.5),
      }));
    }
    if (visual.accent_bar) {
      group.appendChild(createSvg("rect", {
        class: "prism-node-accent", x, y, width: theme.node_accent_bar_width,
        height: node.height, rx: 1, fill: style.border,
      }));
    }
    const iconPath = payload.icons[node.role];
    const iconX = x + config.node_text_padding;
    if (iconPath) {
      const icon = createSvg("svg", {
        class: "prism-node-icon",
        x: iconX,
        y: node.y - config.icon_size / 2,
        width: config.icon_size,
        height: config.icon_size,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: style.text,
        "stroke-width": 1.8,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
      });
      icon.innerHTML = iconPath;
      group.appendChild(icon);
    }
    const textX = iconX + config.icon_size + 12;
    const available = node.width - (textX - x) - config.node_text_padding;
    const titleChars = Math.max(4, Math.floor(available / config.node_title_font_size));
    const subtitleChars = Math.max(6, Math.floor(available / config.node_subtitle_font_size));
    group.appendChild(createSvg("text", {
      x: textX,
      y: node.y - 6,
      fill: style.text,
      "font-size": config.node_title_font_size,
      "font-weight": config.title_font_weight,
      "font-family": "ui-sans-serif, system-ui",
    }, truncate(node.label, titleChars)));
    if (node.sublabel) {
      group.appendChild(createSvg("text", {
        x: textX,
        y: node.y + 18,
        fill: style.text,
        "font-size": config.node_subtitle_font_size,
        "font-weight": 400,
        opacity: config.subtitle_opacity,
        "font-family": "ui-sans-serif, system-ui",
      }, truncate(node.sublabel, subtitleChars)));
    }
  }

  function renderClusters(svg, payload, result) {
    if (!result.clusters.length) return;
    const group = createSvg("g", { class: "parallel-lanes" });
    result.clusters.forEach((cluster) => {
      group.appendChild(createSvg("rect", {
        x: cluster.x - cluster.width / 2,
        y: cluster.y - cluster.height / 2,
        width: cluster.width,
        height: cluster.height,
        rx: 12,
        fill: "none",
        stroke: payload.theme.accent_secondary,
        "stroke-width": 1.5,
        "stroke-dasharray": "7 9",
        opacity: 0.6,
      }));
      group.appendChild(createSvg("text", {
        x: cluster.x,
        y: cluster.y - cluster.height / 2 + 22,
        "text-anchor": "middle",
        fill: payload.theme.text_secondary,
        "font-size": payload.layout.edge_label_font_size,
        "font-weight": 650,
        "font-family": "ui-sans-serif, system-ui",
      }, cluster.title));
    });
    svg.appendChild(group);
  }

  function edgeColorKind(payload, edge) {
    if (!isParallel(payload)) return "primary";
    const laneByNode = Object.fromEntries(payload.prism.nodes.map((node) => [node.id, node.lane]));
    return laneByNode[edge.from] === laneByNode[edge.to] ? "primary" : "secondary";
  }

  function removeDuplicatePoints(points) {
    return points.filter(
      (point, index) =>
        index === 0 ||
        point.x !== points[index - 1].x ||
        point.y !== points[index - 1].y
    );
  }

  function orthogonalPoints(payload, edge, result) {
    if (edge.deferred) return edge.points;
    const source = result.nodes.find((node) => node.id === edge.from);
    const target = result.nodes.find((node) => node.id === edge.to);
    const direction = isParallel(payload) ? "TD" : payload.prism.diagram.direction;
    if (direction === "LR" || direction === "RL") {
      const forward = direction === "LR";
      const start = {
        x: source.x + (forward ? source.width / 2 : -source.width / 2),
        y: source.y,
      };
      const end = {
        x: target.x + (forward ? -target.width / 2 : target.width / 2),
        y: target.y,
      };
      if (Math.abs(start.y - end.y) < 0.1) return [start, end];
      const middleX = (start.x + end.x) / 2;
      return removeDuplicatePoints([
        start,
        { x: middleX, y: start.y },
        { x: middleX, y: end.y },
        end,
      ]);
    }
    const forward = direction !== "BT";
    const start = {
      x: source.x,
      y: source.y + (forward ? source.height / 2 : -source.height / 2),
    };
    const end = {
      x: target.x,
      y: target.y + (forward ? -target.height / 2 : target.height / 2),
    };
    if (Math.abs(start.x - end.x) < 0.1) return [start, end];
    const middleY = (start.y + end.y) / 2;
    return removeDuplicatePoints([
      start,
      { x: start.x, y: middleY },
      { x: end.x, y: middleY },
      end,
    ]);
  }

  function parallelCurveRoute(payload, edge, result) {
    if (!isParallel(payload) || edge.deferred) return null;
    const source = result.nodes.find((node) => node.id === edge.from);
    const target = result.nodes.find((node) => node.id === edge.to);
    const isEntryFanout = edge.from === result.shared.entry;
    const isConvergence = edge.to === result.shared.convergence;
    if (!isEntryFanout && !isConvergence) return null;

    const start = { x: source.x, y: source.y + source.height / 2 };
    const end = { x: target.x, y: target.y - target.height / 2 };
    const curveHeight = Math.max(24, Math.min(payload.layout.fanout_curve_height, Math.abs(end.y - start.y) / 2));
    const controlOne = { x: start.x, y: start.y + curveHeight };
    const controlTwo = { x: end.x, y: end.y - curveHeight };
    return {
      curved: true,
      points: [start, end],
      path: `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${controlOne.x.toFixed(1)} ${controlOne.y.toFixed(1)} ${controlTwo.x.toFixed(1)} ${controlTwo.y.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
      labelPosition: {
        x: (start.x + end.x) / 2,
        y: (start.y + end.y) / 2 - payload.layout.edge_label_font_size / 2 - 2,
        width: estimateTextWidth(edge.label || "", payload.layout.edge_label_font_size),
      },
    };
  }

  function edgeRoute(payload, edge, result) {
    const curve = parallelCurveRoute(payload, edge, result);
    if (curve) return curve;
    const points = orthogonalPoints(payload, edge, result);
    return {
      curved: false,
      points,
      path: points.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" "),
      labelPosition: edge.deferred
        ? {
          x: edge.x,
          y: edge.y,
          width: estimateTextWidth(edge.label || "", payload.layout.edge_label_font_size),
        }
        : null,
    };
  }

  function edgeLabelPosition(points, label, config) {
    const width = estimateTextWidth(label, config.edge_label_font_size);
    const segments = points.slice(0, -1).map((start, index) => {
      const end = points[index + 1];
      return {
        start,
        end,
        horizontal: Math.abs(start.y - end.y) < 0.1,
        length: Math.abs(start.x - end.x) + Math.abs(start.y - end.y),
      };
    });
    const segment = [...segments].sort((left, right) => right.length - left.length)[0];
    if (!segment) return { x: 0, y: 0, width };
    if (segment.horizontal) {
      return {
        x: (segment.start.x + segment.end.x) / 2,
        y: segment.start.y - config.edge_label_font_size / 2 - 2,
        width,
      };
    }
    return {
      x: segment.start.x + width / 2 + 6,
      y: (segment.start.y + segment.end.y) / 2,
      width,
    };
  }

  function renderEdges(svg, payload, result) {
    const pathGroup = createSvg("g", { class: "edges" });
    const labelGroup = createSvg("g", { class: "edge-labels" });
    result.edges.forEach((edge) => {
      const visual = payload.ontology.edge_types[edge.type]?.visual || {};
      const kind = edgeColorKind(payload, edge);
      const color = kind === "primary" ? payload.theme.accent_primary : payload.theme.accent_secondary;
      const route = edgeRoute(payload, edge, result);
      pathGroup.appendChild(createSvg("path", {
        d: route.path,
        "data-edge-type": edge.type,
        fill: "none",
        stroke: color,
        "stroke-width": visual.stroke_width || 1,
        "stroke-dasharray": visual.stroke_dash,
        "marker-end": visual.arrow && visual.arrow !== "none" ? `url(#${visual.arrow}_${kind})` : null,
        opacity: payload.layout.edge_opacity,
      }));
      if (edge.label) {
        const labelPosition = route.labelPosition || edgeLabelPosition(
          route.points, edge.label, payload.layout
        );
        const width = labelPosition.width;
        const height = payload.layout.edge_label_font_size + 6;
        labelGroup.appendChild(createSvg("rect", {
          x: labelPosition.x - width / 2,
          y: labelPosition.y - height / 2,
          width,
          height,
          rx: 2,
          fill: payload.theme.background,
          opacity: 0.94,
        }));
        labelGroup.appendChild(createSvg("text", {
          x: labelPosition.x,
          y: labelPosition.y + payload.layout.edge_label_font_size / 3,
          "text-anchor": "middle",
          fill: payload.theme.text_secondary,
          "font-size": payload.layout.edge_label_font_size,
          opacity: payload.layout.edge_label_opacity,
          "font-family": "ui-sans-serif, system-ui",
        }, edge.label));
      }
    });
    svg.appendChild(pathGroup);
    svg.appendChild(labelGroup);
  }

  function renderLoops(svg, payload, result) {
    if (!payload.prism.render.show_loops || !payload.prism.loops.length) return;
    const config = payload.layout;
    const x = config.node_route_clearance;
    const y = result.graphHeight + 20;
    const width = result.width - 2 * config.node_route_clearance;
    const height = result.loopPanelHeight;
    const group = createSvg("g", { class: "feedback-loops" });
    group.appendChild(createSvg("rect", {
      x, y, width, height, rx: 10,
      fill: payload.theme.background,
      stroke: payload.theme.surface_border,
      "stroke-width": 1,
      opacity: 0.96,
    }));
    group.appendChild(createSvg("text", {
      x: x + 14, y: y + 22,
      fill: payload.theme.text_primary,
      "font-size": config.loop_font_size,
      "font-weight": 650,
      "font-family": "ui-sans-serif, system-ui",
    }, "Feedback loops"));
    payload.prism.loops.slice(0, 2).forEach((loop, index) => {
      group.appendChild(createSvg("text", {
        x: x + 14, y: y + 48 + index * 16,
        fill: payload.theme.text_secondary,
        "font-size": config.loop_font_size,
        "font-family": "ui-sans-serif, system-ui",
      }, truncate(`${loop.label} (${loop.polarity}): ${loop.nodes.join(" → ")}`, 76)));
    });
    svg.appendChild(group);
  }

  function render(payload, container) {
    const result = layout(payload);
    root.__PRISM_LAYOUT__ = result;
    const svg = createSvg("svg", {
      class: "prism-svg",
      role: "img",
      "aria-label": payload.prism.meta.title,
      width: result.width,
      height: result.height,
      viewBox: `0 0 ${result.width} ${result.height}`,
    });
    appendDefinitions(svg, payload);
    svg.appendChild(createSvg("rect", { width: result.width, height: result.height, fill: payload.theme.background }));
    svg.appendChild(createSvg("rect", {
      x: 1, y: 1, width: result.width - 2, height: result.height - 2,
      rx: 16, fill: "none", stroke: payload.theme.surface_border, "stroke-width": 1.5,
    }));
    renderClusters(svg, payload, result);
    renderEdges(svg, payload, result);
    const nodeGroup = createSvg("g", { class: "nodes" });
    result.nodes.forEach((node) => {
      const group = createSvg("g", {
        class: "node",
        "data-node-id": node.id,
        "data-role": node.role,
        "data-status": node.status,
      });
      renderNode(group, payload, node);
      nodeGroup.appendChild(group);
    });
    svg.appendChild(nodeGroup);
    renderLoops(svg, payload, result);
    svg.appendChild(createSvg("text", {
      x: result.width - 16,
      y: result.height - 16,
      "text-anchor": "end",
      fill: payload.theme.watermark_color,
      "font-size": payload.layout.watermark_font_size,
      "font-family": "ui-sans-serif, system-ui",
    }, payload.theme.watermark));
    container.replaceChildren(svg);
    return result;
  }

  root.PrismDagre = {
    buildGraph,
    layout,
    render,
    visibleEdges,
    orthogonalPoints,
    edgeRoute,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
