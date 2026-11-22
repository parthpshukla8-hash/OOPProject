import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Bars, Err, Stat } from "../ui.jsx";

export default function Reports() {
  const [r, setR] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { api("/reports/").then(setR).catch((x) => setErr(x.message)); }, []);
  if (!r) return <Err msg={err} />;
  const o = r.overview;
  return (
    <>
      <h1>Reports & analytics</h1>
      <div className="grid"><Stat label="Total incidents" value={o.total} /><Stat label="Open" value={o.open} /><Stat label="Critical (open P1)" value={o.critical} />
        <Stat label="Resolved" value={o.resolved} /><Stat label="SLA violations" value={o.sla_violations} /><Stat label="Escalated" value={o.escalated} />
        <Stat label="Possible duplicates" value={o.duplicates} /><Stat label="Avg resolution (min)" value={o.avg_resolution_minutes} />
        <Stat label="Avg feedback (/5)" value={o.avg_feedback ? o.avg_feedback.toFixed(1) : null} /></div>
      <div className="two"><div className="card"><h3>Incidents by service</h3><Bars rows={r.by_service} /></div>
        <div className="card"><h3>By priority</h3><Bars rows={r.by_priority} /><h3 style={{ marginTop: 16 }}>By status</h3><Bars rows={r.by_status} /></div></div>
      <div className="two"><div className="card"><h3>Technician workload</h3><table><thead><tr><th>Technician</th><th>Active</th><th>Capacity</th><th></th></tr></thead>
        <tbody>{r.technician_workload.map((t) => <tr key={t.id}><td>{t.name}{!t.available && " (away)"}</td><td>{t.active}</td><td>{t.max_load}</td>
          <td style={{ width: 120 }}><div className="bar"><i style={{ width: `${Math.min(100, (t.active / t.max_load) * 100)}%`, background: t.active >= t.max_load ? "var(--bad)" : "var(--brand)" }} /></div></td></tr>)}</tbody></table></div>
        <div className="card"><h3>By category</h3><Bars rows={r.by_category} /><h3 style={{ marginTop: 16 }}>Correlated incidents</h3>
          {r.correlations.length ? r.correlations.map((c) => <p key={c.service}><b>{c.service}</b>: {c.incidents.join(", ")}</p>) : <p className="mute">No clusters detected.</p>}</div></div>
    </>
  );
}
