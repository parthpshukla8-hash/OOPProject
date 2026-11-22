import { useEffect, useState } from "react";
import { api, fmt } from "../api.js";

export default function Audit() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState("");
  const load = () => api("/audit/" + (q ? `?incident=${encodeURIComponent(q.toUpperCase())}` : "")).then(setRows);
  useEffect(() => { load(); }, []);
  return (
    <>
      <h1>Audit log</h1>
      <div className="row tight" style={{ marginBottom: 12 }}><input placeholder="Filter by incident ID e.g. INC1004" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 280 }} /><button onClick={load}>Filter</button></div>
      <div className="card"><table><thead><tr><th>Time</th><th>User</th><th>Incident</th><th>Action</th><th>Previous</th><th>New</th><th>Description</th></tr></thead>
        <tbody>{rows.map((a) => <tr key={a.id}><td>{fmt(a.timestamp)}</td><td>{a.user}</td><td>{a.incident_number || "—"}</td><td>{a.action}</td><td>{a.previous_state || "—"}</td><td>{a.new_state || "—"}</td><td>{a.description}</td></tr>)}</tbody></table></div>
    </>
  );
}
