import { useEffect, useMemo, useState } from "react";
import { Badge, Text, Title2, tokens } from "@fluentui/react-components";
import { api } from "../api.js";
import { Err, Mute, Section, Two } from "../ui.jsx";

const W = 900, NW = 180, NH = 62, GAP = 130;
const FILL = { critical: tokens.colorPaletteRedBackground2, degraded: tokens.colorPaletteYellowBackground2, ok: tokens.colorPaletteGreenBackground2 };
const EDGE = { critical: tokens.colorPaletteRedBorder2, degraded: tokens.colorPaletteYellowBorder2, ok: tokens.colorPaletteGreenBorder2 };

/** Reachable ids following edges in one direction. */
const reach = (start, edges, key, other) => {
  const seen = new Set(); const stack = [start];
  while (stack.length) { const c = stack.pop(); edges.filter((e) => e[key] === c).forEach((e) => { if (!seen.has(e[other])) { seen.add(e[other]); stack.push(e[other]); } }); }
  return seen;
};

export default function ServiceMap() {
  const [g, setG] = useState(null); const [sel, setSel] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { api("/service-graph/").then(setG).catch((x) => setErr(x.message)); }, []);

  const layout = useMemo(() => {
    if (!g) return null;
    const deps = {}; g.edges.forEach((e) => (deps[e.from] = [...(deps[e.from] || []), e.to]));
    const level = {};
    const lv = (id, stack = []) => {
      if (level[id] !== undefined) return level[id];
      if (stack.includes(id)) return 0;
      level[id] = (deps[id] || []).length ? 1 + Math.max(...deps[id].map((d) => lv(d, [...stack, id]))) : 0;
      return level[id];
    };
    g.nodes.forEach((n) => lv(n.id));
    const max = Math.max(0, ...Object.values(level));
    const rows = {}; g.nodes.forEach((n) => (rows[level[n.id]] = [...(rows[level[n.id]] || []), n]));
    const pos = {};
    Object.entries(rows).forEach(([l, ns]) => ns.forEach((n, i) => { pos[n.id] = { x: ((i + 1) * W) / (ns.length + 1) - NW / 2, y: (max - l) * GAP + 20 }; }));
    return { pos, height: (max + 1) * GAP + 10 };
  }, [g]);

  if (!g) return <Err msg={err} />;
  const byId = Object.fromEntries(g.nodes.map((n) => [n.id, n]));
  const upstream = sel ? reach(sel, g.edges, "from", "to") : new Set();       // what it depends on
  const downstream = sel ? reach(sel, g.edges, "to", "from") : new Set();     // blast radius
  const dim = (id) => sel && id !== sel && !upstream.has(id) && !downstream.has(id);
  const chosen = sel && byId[sel];

  return (
    <>
      <Title2 block style={{ marginBottom: 8 }}>Service dependency map</Title2>
      <Mute block style={{ marginBottom: 16 }}>Live health from open incidents. Arrows point to what a service depends on. Click a service to see its dependencies and blast radius. Incidents on a service are prioritised by the most critical service that relies on it.</Mute>
      <Two>
        <Section>
          <svg viewBox={`0 0 ${W} ${layout.height}`} style={{ width: "100%" }}>
            <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style={{ fill: tokens.colorNeutralStroke1 }} /></marker></defs>
            {g.edges.map((e, i) => {
              const a = layout.pos[e.from], b = layout.pos[e.to];
              const hot = sel && (e.from === sel || e.to === sel || (downstream.has(e.from) || e.from === sel) && (upstream.has(e.to) || e.to === sel));
              return <line key={i} x1={a.x + NW / 2} y1={a.y + NH} x2={b.x + NW / 2} y2={b.y - 2} markerEnd="url(#arrow)"
                style={{ stroke: hot ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke1, strokeWidth: hot ? 2.5 : 1.2, opacity: sel && !hot ? 0.25 : 1 }} />;
            })}
            {g.nodes.map((n) => { const p = layout.pos[n.id]; return (
              <g key={n.id} onClick={() => setSel(sel === n.id ? null : n.id)} style={{ cursor: "pointer", opacity: dim(n.id) ? 0.3 : 1 }}>
                <rect x={p.x} y={p.y} width={NW} height={NH} rx={10} style={{ fill: FILL[n.health], stroke: n.id === sel ? tokens.colorBrandStroke1 : EDGE[n.health], strokeWidth: n.id === sel ? 3 : 1.5 }} />
                <text x={p.x + NW / 2} y={p.y + 26} textAnchor="middle" style={{ fill: tokens.colorNeutralForeground1, fontSize: 13, fontWeight: 600 }}>{n.name.length > 24 ? n.name.slice(0, 23) + "…" : n.name}</text>
                <text x={p.x + NW / 2} y={p.y + 46} textAnchor="middle" style={{ fill: tokens.colorNeutralForeground2, fontSize: 11 }}>criticality {n.criticality} · {n.open} open</text>
              </g>); })}
          </svg>
          <Mute>Legend: <Badge color="success" appearance="tint">healthy</Badge> <Badge color="warning" appearance="tint">open incidents</Badge> <Badge color="danger" appearance="tint">open P1</Badge></Mute>
        </Section>
        <Section title={chosen ? chosen.name : "Select a service"}>
          {!chosen && <Mute>Click a node to analyse dependencies.</Mute>}
          {chosen && <>
            <Text>Criticality {chosen.criticality} · {chosen.open} open incident(s)</Text>
            <Text weight="semibold">Depends on</Text>
            {upstream.size ? [...upstream].map((id) => <Text key={id}>• {byId[id].name} {byId[id].open > 0 && <Badge color="danger" size="small">{byId[id].open} open</Badge>}</Text>) : <Mute>Nothing (foundation service)</Mute>}
            <Text weight="semibold">If it fails, impacts</Text>
            {downstream.size ? [...downstream].map((id) => <Text key={id}>• {byId[id].name} (criticality {byId[id].criticality})</Text>) : <Mute>No other service</Mute>}</>}
        </Section>
      </Two>
    </>
  );
}
