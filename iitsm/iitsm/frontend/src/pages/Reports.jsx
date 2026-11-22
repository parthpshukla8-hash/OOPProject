import { useEffect, useState } from "react";
import { ProgressBar, Text, Title2 } from "@fluentui/react-components";
import { api } from "../api.js";
import { Bars, DTable, Err, Grid, Mute, Section, Stat, Two } from "../ui.jsx";

export default function Reports() {
  const [r, setR] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { api("/reports/").then(setR).catch((x) => setErr(x.message)); }, []);
  if (!r) return <Err msg={err} />;
  const o = r.overview;
  return (
    <>
      <Title2 block style={{ marginBottom: 16 }}>Reports & analytics</Title2>
      <Grid><Stat label="Total incidents" value={o.total} /><Stat label="Open" value={o.open} /><Stat label="Critical (open P1)" value={o.critical} />
        <Stat label="Resolved" value={o.resolved} /><Stat label="SLA violations" value={o.sla_violations} /><Stat label="Escalated" value={o.escalated} />
        <Stat label="Possible duplicates" value={o.duplicates} /><Stat label="Avg resolution (min)" value={o.avg_resolution_minutes} />
        <Stat label="Avg feedback (/5)" value={o.avg_feedback ? o.avg_feedback.toFixed(1) : null} /></Grid>
      <Two>
        <Section title="Incidents by service"><Bars rows={r.by_service} /></Section>
        <Section title="By priority"><Bars rows={r.by_priority} /><Text weight="semibold">By status</Text><Bars rows={r.by_status} /></Section>
      </Two>
      <Two>
        <Section title="Technician workload"><DTable rows={r.technician_workload} cols={[
          { h: "Technician", render: (t) => <>{t.name}{!t.available && " (away)"}</> }, { h: "Active", render: (t) => t.active }, { h: "Capacity", render: (t) => t.max_load },
          { h: "Load", render: (t) => <ProgressBar value={t.active} max={t.max_load} color={t.active >= t.max_load ? "error" : "brand"} thickness="large" style={{ minWidth: 100 }} /> }]} /></Section>
        <Section title="By category"><Bars rows={r.by_category} /><Text weight="semibold">Correlated incidents</Text>
          {r.correlations.length ? r.correlations.map((c) => <div key={c.service}><b>{c.service}</b>: {c.incidents.join(", ")}</div>) : <Mute>No clusters detected.</Mute>}</Section>
      </Two>
    </>
  );
}
