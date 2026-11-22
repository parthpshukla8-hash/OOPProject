import { useEffect, useState } from "react";
import { Button, Input, Title2 } from "@fluentui/react-components";
import { api, fmt } from "../api.js";
import { DTable, Row, Section } from "../ui.jsx";

export default function Audit() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState("");
  const load = () => api("/audit/" + (q ? `?incident=${encodeURIComponent(q.toUpperCase())}` : "")).then(setRows);
  useEffect(() => { load(); }, []);
  return (
    <>
      <Title2 block style={{ marginBottom: 16 }}>Audit log</Title2>
      <Row style={{ marginBottom: 12 }}><Input placeholder="Filter by incident ID e.g. INC1004" value={q} onChange={(e, d) => setQ(d.value)} style={{ minWidth: 280 }} onKeyDown={(e) => e.key === "Enter" && load()} />
        <Button appearance="primary" onClick={load}>Filter</Button></Row>
      <Section><DTable rows={rows} cols={[
        { h: "Time", render: (a) => fmt(a.timestamp) }, { h: "User", render: (a) => a.user }, { h: "Incident", render: (a) => a.incident_number || "—" },
        { h: "Action", render: (a) => a.action }, { h: "Previous", render: (a) => a.previous_state || "—" }, { h: "New", render: (a) => a.new_state || "—" },
        { h: "Description", render: (a) => a.description }]} /></Section>
    </>
  );
}
