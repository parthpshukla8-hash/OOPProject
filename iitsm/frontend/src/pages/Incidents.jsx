import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Badge, Err } from "../ui.jsx";

const STATUSES = ["NEW", "CLASSIFIED", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "AWAITING_INFO", "RESOLVED", "VERIFIED", "CLOSED"];

export default function Incidents() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({});
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]); const [svcs, setSvcs] = useState([]); const [techs, setTechs] = useState([]);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const search = () => {
    const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
    api("/incidents/?" + qs).then(setRows).catch((x) => setErr(x.message));
  };
  useEffect(() => {
    search(); api("/categories/").then(setCats); api("/services/").then(setSvcs);
    if (user.role === "ADMIN") api("/technicians/").then(setTechs);
  }, []);

  const Sel = ({ k, label, opts }) => (<div><label>{label}</label><select value={f[k] || ""} onChange={set(k)}><option value="">Any</option>{opts.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>);
  return (
    <>
      <h1>{user.role === "ADMIN" ? "All incidents" : user.role === "TECHNICIAN" ? "Assigned incidents" : "My incidents"}</h1>
      <div className="card">
        <div className="row"><div><label>Search (ID, title, text)</label><input value={f.q || ""} onChange={set("q")} onKeyDown={(e) => e.key === "Enter" && search()} /></div>
          <Sel k="status" label="Status" opts={STATUSES.map((s) => [s, s.replace("_", " ")])} />
          <Sel k="priority" label="Priority" opts={["P1", "P2", "P3", "P4"].map((p) => [p, p])} />
          <Sel k="category" label="Category" opts={cats.map((c) => [c.id, c.name])} />
          <Sel k="service" label="Service" opts={svcs.map((s) => [s.id, s.name])} />
          {user.role === "ADMIN" && <Sel k="technician" label="Technician" opts={techs.map((t) => [t.id, t.name])} />}
          <Sel k="sla_status" label="SLA status" opts={["ON_TRACK", "AT_RISK", "BREACHED", "MET"].map((s) => [s, s.replace("_", " ")])} />
          <div><label>From</label><input type="date" value={f.date_from || ""} onChange={set("date_from")} /></div>
          <div><label>To</label><input type="date" value={f.date_to || ""} onChange={set("date_to")} /></div>
          <div className="row tight"><button onClick={search}>Search</button><button className="ghost" onClick={() => { setF({}); setTimeout(search, 0); }}>Reset</button></div></div>
      </div>
      <Err msg={err} />
      <div className="card"><table><thead><tr><th>ID</th><th>Title</th><th>Service</th><th>Category</th><th>Priority</th><th>Status</th><th>Technician</th><th>SLA</th><th>Created</th></tr></thead>
        <tbody>{rows.map((i) => (
          <tr key={i.id} className="click" onClick={() => nav(`/incidents/${i.id}`)}>
            <td>{i.number}</td><td>{i.title}{i.duplicate_of_number && <div className="mute">possible duplicate of {i.duplicate_of_number}</div>}</td>
            <td>{i.service_name}</td><td>{i.category_name}</td><td><Badge v={i.priority} /></td><td>{i.status.replace("_", " ")}</td>
            <td>{i.assignee?.name || "—"}</td><td><Badge v={i.sla_status} /></td><td>{fmt(i.created_at)}</td></tr>))}</tbody></table>
        {!rows.length && <p className="mute">No incidents match.</p>}</div>
    </>
  );
}
