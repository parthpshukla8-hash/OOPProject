import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Err, Msg } from "../ui.jsx";

/** Generic CRUD table used for users, services, categories and SLA policies. */
function Crud({ endpoint, fields, empty, canDelete = true }) {
  const [rows, setRows] = useState([]); const [form, setForm] = useState(empty); const [editing, setEditing] = useState(null);
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const load = () => api(endpoint).then(setRows).catch((x) => setErr(x.message));
  useEffect(() => { load(); setForm(empty); setEditing(null); }, [endpoint]);
  const save = async (e) => {
    e.preventDefault(); setErr(""); setOk("");
    try {
      const body = { ...form }; if (editing && !body.password) delete body.password;
      await api(editing ? `${endpoint}${editing}/` : endpoint, { method: editing ? "PATCH" : "POST", body });
      setOk("Saved"); setForm(empty); setEditing(null); load();
    } catch (x) { setErr(x.message); }
  };
  const del = async (id) => { if (confirm("Delete / deactivate this record?")) { try { await api(`${endpoint}${id}/`, { method: "DELETE" }); load(); } catch (x) { setErr(x.message); } } };
  const input = (f) => {
    const v = form[f.key] ?? "";
    const set = (val) => setForm({ ...form, [f.key]: val });
    if (f.type === "select") return <select value={v} onChange={(e) => set(e.target.value)}>{f.options.map(([o, t]) => <option key={o} value={o}>{t}</option>)}</select>;
    if (f.type === "bool") return <select value={String(v)} onChange={(e) => set(e.target.value === "true")}><option value="true">Yes</option><option value="false">No</option></select>;
    if (f.type === "multi") return <select multiple value={form[f.key] || []} onChange={(e) => set([...e.target.selectedOptions].map((o) => +o.value))} style={{ height: 90 }}>{f.options.map(([o, t]) => <option key={o} value={o}>{t}</option>)}</select>;
    return <input type={f.type || "text"} value={v} onChange={(e) => set(f.type === "number" ? +e.target.value : e.target.value)} required={f.required} />;
  };
  const show = (r, f) => f.type === "bool" ? (r[f.key] ? "Yes" : "No") : f.type === "multi" ? (r[f.key] || []).map((id) => f.options.find(([o]) => o === id)?.[1]).filter(Boolean).join(", ") :
    f.type === "select" ? f.options.find(([o]) => o === r[f.key])?.[1] ?? r[f.key] : r[f.key];
  const cols = fields.filter((f) => !f.hideInTable);
  return (
    <>
      <Err msg={err} /><Msg msg={ok} />
      <div className="card"><h3>{editing ? "Edit" : "Add new"}</h3><form onSubmit={save}><div className="row">{fields.map((f) => <div key={f.key}><label>{f.label}</label>{input(f)}</div>)}</div>
        <div className="row tight" style={{ marginTop: 10 }}><button>{editing ? "Update" : "Add"}</button>{editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm(empty); }}>Cancel</button>}</div></form></div>
      <div className="card"><table><thead><tr>{cols.map((f) => <th key={f.key}>{f.label}</th>)}<th /></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id}>{cols.map((f) => <td key={f.key}>{String(show(r, f) ?? "")}</td>)}
          <td className="row tight"><a href="#" onClick={(e) => { e.preventDefault(); setEditing(r.id); setForm({ ...empty, ...r, password: "" }); window.scrollTo(0, 0); }}>edit</a>
            {canDelete && <a href="#" onClick={(e) => { e.preventDefault(); del(r.id); }} style={{ color: "var(--bad)" }}>delete</a>}</td></tr>)}</tbody></table></div>
    </>
  );
}

function Settings() {
  const [s, setS] = useState(null); const [ok, setOk] = useState(""); const [err, setErr] = useState("");
  useEffect(() => { api("/settings/").then(setS); }, []);
  const save = async (k, v) => { try { setS(await api("/settings/", { method: "PATCH", body: { [k]: v } })); setOk("Strategy updated – applies to the next incident"); } catch (x) { setErr(x.message); } };
  if (!s) return null;
  const A = [["SKILL", "Skill based"], ["LOAD", "Load based"], ["ROUND_ROBIN", "Round robin"], ["SMART", "Smart (skills + load + experience + history)"]];
  const P = [["WEIGHTED", "Weighted score (Impact × Urgency × Criticality)"], ["RULE", "Rule based (weighted + critical-service override)"]];
  return <div className="card"><Err msg={err} /><Msg msg={ok} /><label>Technician assignment strategy</label>
    <select value={s.assignment_strategy} onChange={(e) => save("assignment_strategy", e.target.value)}>{A.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
    <label>Priority calculation strategy</label><select value={s.priority_strategy} onChange={(e) => save("priority_strategy", e.target.value)}>{P.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>;
}

export default function Admin() {
  const [tab, setTab] = useState("users");
  const [cats, setCats] = useState([]); const [svcs, setSvcs] = useState([]);
  useEffect(() => { api("/categories/").then(setCats); api("/services/").then(setSvcs); }, [tab]);
  const co = cats.map((c) => [c.id, c.name]);
  const tabs = {
    users: <Crud endpoint="/users/" empty={{ username: "", first_name: "", last_name: "", email: "", role: "TECHNICIAN", skills: [], experience_years: 0, max_load: 5, is_available: true, is_active: true, password: "" }}
      fields={[{ key: "username", label: "Username", required: true }, { key: "first_name", label: "First name" }, { key: "last_name", label: "Last name" }, { key: "email", label: "Email", type: "email", hideInTable: true },
        { key: "role", label: "Role", type: "select", options: [["EMPLOYEE", "Employee"], ["TECHNICIAN", "Technician"], ["ADMIN", "Administrator"]] },
        { key: "skills", label: "Skills (technicians)", type: "multi", options: co }, { key: "experience_years", label: "Experience (yrs)", type: "number" },
        { key: "max_load", label: "Max load", type: "number" }, { key: "is_available", label: "Available", type: "bool" }, { key: "is_active", label: "Active", type: "bool" },
        { key: "password", label: "Password (blank = keep)", type: "password", hideInTable: true }]} />,
    services: <Crud endpoint="/services/" empty={{ name: "", description: "", business_criticality: 3 }}
      fields={[{ key: "name", label: "Service", required: true }, { key: "description", label: "Description" }, { key: "business_criticality", label: "Business criticality (1-5)", type: "number" }]} />,
    categories: <Crud endpoint="/categories/" empty={{ name: "", keywords: "" }}
      fields={[{ key: "name", label: "Category", required: true }, { key: "keywords", label: "Auto-detect keywords (comma separated)" }]} />,
    sla: <Crud endpoint="/sla-policies/" empty={{ service: "", priority: "P1", response_minutes: 5, resolution_minutes: 30 }}
      fields={[{ key: "service", label: "Service (blank = default)", type: "select", options: [["", "(default for all)"], ...svcs.map((s) => [s.id, s.name])] },
        { key: "priority", label: "Priority", type: "select", options: ["P1", "P2", "P3", "P4"].map((p) => [p, p]) },
        { key: "response_minutes", label: "Response target (min)", type: "number" }, { key: "resolution_minutes", label: "Resolution target (min)", type: "number" }]} />,
    settings: <Settings />,
  };
  return (
    <>
      <h1>Administration</h1>
      <div className="row tight" style={{ marginBottom: 12 }}>{[["users", "Users & technicians"], ["services", "IT services"], ["categories", "Categories"], ["sla", "SLA policies"], ["settings", "Strategies"]].map(([k, t]) =>
        <button key={k} className={tab === k ? "" : "ghost"} onClick={() => setTab(k)}>{t}</button>)}</div>
      {tabs[tab]}
    </>
  );
}
