/** Shared Fluent UI v9 building blocks used by every page. */
import { useNavigate } from "react-router-dom";
import {
  Badge, Card, Field, Input, MessageBar, MessageBarBody, ProgressBar, Select, Table, TableBody, TableCell,
  TableHeader, TableHeaderCell, TableRow, Text, Textarea, makeStyles, tokens,
} from "@fluentui/react-components";
import { fmt } from "./api.js";

const useS = makeStyles({
  row: { display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "flex-end" },
  grid: { display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", marginBottom: "16px" },
  two: { display: "grid", gap: "16px", gridTemplateColumns: "2fr 1fr", alignItems: "start", "@media (max-width: 900px)": { gridTemplateColumns: "1fr" } },
  section: { marginBottom: "16px", padding: "16px" },
  stat: { padding: "14px" },
  kv: { display: "grid", gridTemplateColumns: "140px 1fr", gap: "6px 12px" },
  tl: { borderLeft: `2px solid ${tokens.colorNeutralStroke2}`, paddingLeft: "14px", marginLeft: "6px", display: "grid", gap: "10px" },
});

export const Row = ({ children, style }) => { const s = useS(); return <div className={s.row} style={style}>{children}</div>; };
export const Grid = ({ children }) => { const s = useS(); return <div className={s.grid}>{children}</div>; };
export const Two = ({ children }) => { const s = useS(); return <div className={s.two}>{children}</div>; };
export const Mute = ({ children, ...r }) => <Text size={200} style={{ color: tokens.colorNeutralForeground3 }} {...r}>{children}</Text>;

export const Section = ({ title, action, children, ...r }) => {
  const s = useS();
  return (
    <Card className={s.section} {...r}>
      {(title || action) && <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><Text weight="semibold" size={400}>{title}</Text>{action}</div>}
      {children}
    </Card>
  );
};

export const Stat = ({ label, value }) => {
  const s = useS();
  return <Card className={s.stat} size="small"><Text size={800} weight="semibold">{value ?? "—"}</Text><Mute>{label}</Mute></Card>;
};

export const KV = ({ rows }) => {
  const s = useS();
  return <div className={s.kv}>{rows.filter(Boolean).map(([k, v]) => [<Mute key={k + "k"} size={300}>{k}</Mute>, <Text key={k + "v"} style={{ whiteSpace: "pre-wrap" }}>{v}</Text>])}</div>;
};

export const Timeline = ({ items }) => {
  const s = useS();
  return <div className={s.tl}>{items.map((h) => <div key={h.id}><Mute block>{fmt(h.timestamp)} · {h.user}</Mute><Text size={300}>{h.description}</Text></div>)}</div>;
};

export const Bars = ({ rows }) => {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div style={{ display: "grid", gap: 8 }}>{rows.map((r) => (
      <div key={r.label}><div style={{ display: "flex", justifyContent: "space-between" }}><Text size={300}>{r.label}</Text><Text weight="semibold">{r.count}</Text></div>
        <ProgressBar value={r.count} max={max} thickness="large" /></div>))}</div>
  );
};

// ---- badges
const PRIORITY = { P1: "danger", P2: "severe", P3: "informative", P4: "success" };
const SLA = { BREACHED: "danger", AT_RISK: "warning", ON_TRACK: "success", MET: "success" };
export const PBadge = ({ v }) => <Badge appearance="filled" color={PRIORITY[v] || "informative"}>{v}</Badge>;
export const SlaBadge = ({ v }) => <Badge appearance="tint" color={SLA[v] || "informative"}>{String(v).replace("_", " ")}</Badge>;
export const StatusBadge = ({ v }) => <Badge appearance="outline" color="brand">{String(v).replace("_", " ")}</Badge>;
export const ChannelBadge = ({ v }) => <Badge appearance="tint" color="brand">{v.replace("_", "-")}</Badge>;

// ---- messages
export const Err = ({ msg }) => (msg ? <MessageBar intent="error" style={{ marginBottom: 12 }}><MessageBarBody>{msg}</MessageBarBody></MessageBar> : null);
export const Msg = ({ msg }) => (msg ? <MessageBar intent="success" style={{ marginBottom: 12 }}><MessageBarBody>{msg}</MessageBarBody></MessageBar> : null);
export const Hint = ({ intent = "warning", children }) => <MessageBar intent={intent} style={{ marginBottom: 12 }}><MessageBarBody>{children}</MessageBarBody></MessageBar>;

// ---- form controls (Field + control, value-based onChange)
const flex = { flex: "1 1 160px", minWidth: 140 };
export const Txt = ({ label, value, onChange, required, ...r }) => (
  <Field label={label} required={required} style={flex}><Input value={String(value ?? "")} onChange={(e, d) => onChange(d.value)} {...r} /></Field>
);
export const Area = ({ label, value, onChange, ...r }) => (
  <Field label={label} style={{ width: "100%" }}><Textarea value={value} onChange={(e, d) => onChange(d.value)} resize="vertical" {...r} /></Field>
);
export const Sel = ({ label, value, onChange, options, any, ...r }) => (
  <Field label={label} style={flex}>
    <Select value={String(value ?? "")} onChange={(e, d) => onChange(d.value)} {...r}>
      {any !== undefined && <option value="">{any}</option>}
      {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
    </Select>
  </Field>
);

// ---- tables
export function DTable({ cols, rows, onRow, empty = "Nothing here yet." }) {
  if (!rows.length) return <Mute>{empty}</Mute>;
  return (
    <div style={{ overflowX: "auto" }}>
      <Table size="small" aria-label="data table">
        <TableHeader><TableRow>{cols.map((c) => <TableHeaderCell key={c.h}>{c.h}</TableHeaderCell>)}</TableRow></TableHeader>
        <TableBody>{rows.map((r, i) => (
          <TableRow key={r.id ?? i} onClick={onRow ? () => onRow(r) : undefined} style={onRow ? { cursor: "pointer" } : undefined}>
            {cols.map((c) => <TableCell key={c.h}>{c.render(r)}</TableCell>)}
          </TableRow>))}</TableBody>
      </Table>
    </div>
  );
}

export function IncidentTable({ rows, empty }) {
  const nav = useNavigate();
  return (
    <DTable rows={rows} empty={empty} onRow={(r) => nav(`/incidents/${r.id}`)} cols={[
      { h: "ID", render: (i) => <Text weight="semibold">{i.number}</Text> },
      { h: "Title", render: (i) => <>{i.title}{i.duplicate_of_number && <Mute block>possible duplicate of {i.duplicate_of_number}</Mute>}</> },
      { h: "Service", render: (i) => i.service_name },
      { h: "Priority", render: (i) => <PBadge v={i.priority} /> },
      { h: "Status", render: (i) => <StatusBadge v={i.status} /> },
      { h: "Technician", render: (i) => i.assignee?.name || "—" },
      { h: "SLA", render: (i) => <SlaBadge v={i.sla_status} /> },
      { h: "Created", render: (i) => fmt(i.created_at) },
    ]} />
  );
}
