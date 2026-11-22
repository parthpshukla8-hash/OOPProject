import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, ProgressBar, Switch, Text, Title2 } from "@fluentui/react-components";
import { Add24Regular } from "@fluentui/react-icons";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { DTable, Err, Grid, Hint, IncidentTable, Mute, PBadge, Section, Stat } from "../ui.jsx";

export default function Dashboard() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
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
      <Title2 block style={{ marginBottom: 16 }}>Welcome, {user.name}</Title2><Err msg={err} />
      {user.role === "EMPLOYEE" && <>
        <Grid><Stat label="My incidents" value={inc.length} /><Stat label="Open" value={open.length} /><Stat label="Resolved / closed" value={inc.length - open.length} /></Grid>
        <Section title="My recent incidents" action={<Button appearance="primary" icon={<Add24Regular />} onClick={() => nav("/new")}>Report incident</Button>}>
          <IncidentTable rows={inc.slice(0, 8)} /></Section></>}

      {user.role === "TECHNICIAN" && <>
        <Grid><Stat label="Active workload" value={`${user.active_load} / ${user.max_load}`} /><Stat label="Open assigned incidents" value={open.length} />
          <Stat label="Experience (years)" value={user.experience_years} /></Grid>
        <Section title="Availability"><Switch checked={user.is_available} onChange={toggle} label={user.is_available ? "Available for new assignments" : "Unavailable – not receiving assignments"} /></Section>
        <Section title="Awaiting action"><IncidentTable rows={open} /></Section></>}

      {user.role === "ADMIN" && rep && <>
        <Grid><Stat label="Total" value={rep.overview.total} /><Stat label="Open" value={rep.overview.open} /><Stat label="Critical (open P1)" value={rep.overview.critical} />
          <Stat label="Resolved" value={rep.overview.resolved} /><Stat label="SLA violations" value={rep.overview.sla_violations} /><Stat label="Escalated" value={rep.overview.escalated} /></Grid>
        {sla && <Mute block style={{ marginBottom: 12 }}>SLA monitor ran: {sla.warnings} warnings · {sla.breaches} new violations · {sla.escalations} escalations (auto-refresh every 60 s)</Mute>}
        {rep.correlations.length > 0 && <Hint><b>Possible common cause:</b> {rep.correlations.map((c) => `${c.count} open incidents on ${c.service} (${c.incidents.join(", ")})`).join("; ")}</Hint>}
        <Section title="Predicted SLA breaches (AI-style risk scoring)">
          <DTable rows={rep.predicted_breaches} empty="No open incidents." onRow={(r) => nav(`/incidents/${r.id}`)} cols={[
            { h: "Incident", render: (r) => <Text weight="semibold">{r.number}</Text> }, { h: "Title", render: (r) => r.title }, { h: "Priority", render: (r) => <PBadge v={r.priority} /> },
            { h: "Predicted time", render: (r) => `${r.predicted_minutes} of ${r.window_minutes} min` },
            { h: "Breach probability", render: (r) => <div style={{ minWidth: 140 }}><Text size={200}>{Math.round(r.probability * 100)}% · {r.level}</Text>
              <ProgressBar value={r.probability} max={1} thickness="large" color={r.level === "HIGH" ? "error" : r.level === "MEDIUM" ? "warning" : "success"} /></div> }]} /></Section>
        <Section title="Needs attention (SLA breached / at risk)"><IncidentTable rows={inc.filter((i) => ["BREACHED", "AT_RISK"].includes(i.sla_status) && i.status !== "CLOSED").slice(0, 8)} /></Section>
        <Section title="Unassigned incidents"><IncidentTable rows={inc.filter((i) => !i.assignee && i.status === "CLASSIFIED")} /></Section></>}
    </>
  );
}
