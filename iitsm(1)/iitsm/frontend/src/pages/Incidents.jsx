import { useEffect, useState } from "react";
import { Button, Input, Field, Title2 } from "@fluentui/react-components";
import { Search24Regular } from "@fluentui/react-icons";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Err, IncidentTable, Row, Section, Sel } from "../ui.jsx";

const STATUSES = ["NEW", "CLASSIFIED", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "AWAITING_INFO", "RESOLVED", "VERIFIED", "CLOSED"];
const pretty = (s) => s.replace("_", " ");

export default function Incidents() {
  const { user } = useAuth();
  const [f, setF] = useState({});
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]); const [svcs, setSvcs] = useState([]); const [techs, setTechs] = useState([]);
  const [err, setErr] = useState("");
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));

  const search = (filters = f) => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    api("/incidents/?" + qs).then(setRows).catch((x) => setErr(x.message));
  };
  useEffect(() => {
    search(); api("/categories/").then(setCats); api("/services/").then(setSvcs);
    if (user.role === "ADMIN") api("/technicians/").then(setTechs);
  }, []);

  return (
    <>
      <Title2 block style={{ marginBottom: 16 }}>{user.role === "ADMIN" ? "All incidents" : user.role === "TECHNICIAN" ? "Assigned incidents" : "My incidents"}</Title2>
      <Section title="Search & filter">
        <Row>
          <Field label="Search (ID, title, text)" style={{ flex: "2 1 240px" }}>
            <Input value={f.q || ""} onChange={(e, d) => set("q")(d.value)} onKeyDown={(e) => e.key === "Enter" && search()} contentBefore={<Search24Regular />} /></Field>
          <Sel label="Status" any="Any" value={f.status} onChange={set("status")} options={STATUSES.map((s) => [s, pretty(s)])} />
          <Sel label="Priority" any="Any" value={f.priority} onChange={set("priority")} options={["P1", "P2", "P3", "P4"].map((p) => [p, p])} />
          <Sel label="Category" any="Any" value={f.category} onChange={set("category")} options={cats.map((c) => [c.id, c.name])} />
          <Sel label="Service" any="Any" value={f.service} onChange={set("service")} options={svcs.map((s) => [s.id, s.name])} />
          {user.role === "ADMIN" && <Sel label="Technician" any="Any" value={f.technician} onChange={set("technician")} options={techs.map((t) => [t.id, t.name])} />}
          <Sel label="SLA status" any="Any" value={f.sla_status} onChange={set("sla_status")} options={["ON_TRACK", "AT_RISK", "BREACHED", "MET"].map((s) => [s, pretty(s)])} />
          <Field label="From" style={{ flex: "1 1 150px" }}><Input type="date" value={f.date_from || ""} onChange={(e, d) => set("date_from")(d.value)} /></Field>
          <Field label="To" style={{ flex: "1 1 150px" }}><Input type="date" value={f.date_to || ""} onChange={(e, d) => set("date_to")(d.value)} /></Field>
          <Button appearance="primary" onClick={() => search()}>Search</Button>
          <Button onClick={() => { setF({}); search({}); }}>Reset</Button>
        </Row>
      </Section>
      <Err msg={err} />
      <Section><IncidentTable rows={rows} empty="No incidents match." /></Section>
    </>
  );
}
