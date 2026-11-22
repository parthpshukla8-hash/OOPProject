import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, fmt } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Badge, Err, Stat } from "../ui.jsx";

function IncidentTable({ rows }) {
  const nav = useNavigate();
  if (!rows.length) return <p className="mute">Nothing here yet.</p>;
  return (
    <table><thead><tr><th>ID</th><th>Title</th><th>Priority</th><th>Status</th><th>SLA</th><th>Created</th></tr></thead>
      <tbody>{rows.map((i) => (
        <tr key={i.id} className="click" onClick={() => nav(`/incidents/${i.id}`)}>
          <td>{i.number}</td><td>{i.title}</td><td><Badge v={i.priority} /></td><td>{i.status.replace("_", " ")}</td>
          <td><Badge v={i.sla_status} /></td><td>{fmt(i.created_at)}</td></tr>))}</tbody></table>
  );
}

export default function Dashboard() {
  const { user, refresh } = useAuth();
  const [inc, setInc] = useState([]);
  const [rep, setRep] = useState(null);
  const [sla, setSla] = useState(null);
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      setInc(await api("/incidents/"));
      if (user.role === "ADMIN") {
        setSla(await api("/sla/check/", { method: "POST" }));   // doubles as a background SLA monitor tick
        setRep(await api("/reports/"));
      }
    } catch (x) { setErr(x.message); }
  };
  useEffect(() => { load(); if (user.role === "ADMIN") { const t = setInterval(load, 60000); return () => clearInterval(t); } }, []);

  const open = inc.filter((i) => !["RESOLVED", "VERIFIED", "CLOSED"].includes(i.status));
  const toggle = async () => { await api("/auth/availability/", { method: "POST" }); refresh(); };

  return (
    <>
      <h1>Welcome, {user.name}</h1><Err msg={err} />
      {user.role === "EMPLOYEE" && <>
        <div className="grid"><Stat label="My incidents" value={inc.length} /><Stat label="Open" value={open.length} />
          <Stat label="Resolved / closed" value={inc.length - open.length} /></div>
        <div className="card"><div className="row tight" style={{ justifyContent: "space-between", display: "flex" }}><h3>My recent incidents</h3><Link to="/new"><button>+ Report incident</button></Link></div><IncidentTable rows={inc.slice(0, 8)} /></div></>}

      {user.role === "TECHNICIAN" && <>
        <div className="grid"><Stat label="Active workload" value={`${user.active_load} / ${user.max_load}`} /><Stat label="Open assigned" value={open.length} />
          <Stat label="Experience (yrs)" value={user.experience_years} />
          <div className="stat"><b>{user.is_available ? "Available" : "Unavailable"}</b><button className="ghost" onClick={toggle}>Toggle availability</button></div></div>
        <div className="card"><h3>Awaiting action</h3><IncidentTable rows={open} /></div></>}

      {user.role === "ADMIN" && rep && <>
        <div className="grid"><Stat label="Total" value={rep.overview.total} /><Stat label="Open" value={rep.overview.open} />
          <Stat label="Critical (P1 open)" value={rep.overview.critical} /><Stat label="Resolved" value={rep.overview.resolved} />
          <Stat label="SLA violations" value={rep.overview.sla_violations} /><Stat label="Escalated" value={rep.overview.escalated} /></div>
        {sla && <p className="mute">SLA monitor ran: {sla.warnings} warnings · {sla.breaches} new violations · {sla.escalations} escalations (auto-refresh every 60 s)</p>}
        {rep.correlations.length > 0 && <div className="hint"><b>Possible common cause:</b> {rep.correlations.map((c) => `${c.count} open incidents on ${c.service} (${c.incidents.join(", ")})`).join("; ")}</div>}
        <div className="card"><h3>Needs attention (SLA breached / at risk)</h3>
          <IncidentTable rows={inc.filter((i) => ["BREACHED", "AT_RISK"].includes(i.sla_status) && !["CLOSED"].includes(i.status)).slice(0, 8)} /></div>
        <div className="card"><h3>Unassigned incidents</h3><IncidentTable rows={inc.filter((i) => !i.assignee && i.status === "CLASSIFIED")} /></div></>}
    </>
  );
}
export { IncidentTable };
