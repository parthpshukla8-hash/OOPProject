import { useEffect, useState } from "react";
import { Button, Dropdown, Field, Option, Switch, Tab, TabList, Title2 } from "@fluentui/react-components";
import { Delete24Regular, Edit24Regular } from "@fluentui/react-icons";
import { api } from "../api.js";
import { DTable, Err, Msg, Row, Section, Sel, Txt } from "../ui.jsx";

/** Generic CRUD screen used for users, services, categories and SLA policies. */
function Crud({ endpoint, fields, empty }) {
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

  const control = (f) => {
    const set = (v) => setForm((x) => ({ ...x, [f.key]: v }));
    if (f.type === "select") return <Sel key={f.key} label={f.label} value={form[f.key]} onChange={set} options={f.options} />;
    if (f.type === "bool") return <Field key={f.key} label={f.label} style={{ flex: "1 1 160px" }}><Switch checked={!!form[f.key]} onChange={(e, d) => set(d.checked)} /></Field>;
    if (f.type === "multi") {
      const sel = (form[f.key] || []).map(String);
      return (
        <Field key={f.key} label={f.label} style={{ flex: "1 1 200px" }}>
          <Dropdown multiselect selectedOptions={sel} value={f.options.filter(([o]) => sel.includes(String(o))).map(([, t]) => t).join(", ")}
            onOptionSelect={(e, d) => set(d.selectedOptions.map(Number))}>
            {f.options.map(([o, t]) => <Option key={o} value={String(o)}>{t}</Option>)}</Dropdown>
        </Field>);
    }
    return <Txt key={f.key} label={f.label} type={f.type || "text"} required={f.required} value={form[f.key]} onChange={(v) => set(f.type === "number" ? +v : v)} />;
  };
  const show = (r, f) => f.type === "bool" ? (r[f.key] ? "Yes" : "No")
    : f.type === "multi" ? (r[f.key] || []).map((id) => f.options.find(([o]) => o === id)?.[1]).filter(Boolean).join(", ")
    : f.type === "select" ? (f.options.find(([o]) => o === r[f.key])?.[1] ?? r[f.key]) : r[f.key];

  return (
    <>
      <Err msg={err} /><Msg msg={ok} />
      <Section title={editing ? "Edit record" : "Add new"}>
        <form onSubmit={save} style={{ display: "grid", gap: 12 }}>
          <Row>{fields.map(control)}</Row>
          <Row style={{ alignItems: "center" }}><Button appearance="primary" type="submit">{editing ? "Update" : "Add"}</Button>
            {editing && <Button onClick={() => { setEditing(null); setForm(empty); }}>Cancel</Button>}</Row>
        </form>
      </Section>
      <Section><DTable rows={rows} cols={[
        ...fields.filter((f) => !f.hideInTable).map((f) => ({ h: f.label, render: (r) => String(show(r, f) ?? "") })),
        { h: "", render: (r) => <>
          <Button size="small" appearance="subtle" icon={<Edit24Regular />} aria-label="Edit" onClick={() => { setEditing(r.id); setForm({ ...empty, ...r, password: "" }); window.scrollTo(0, 0); }} />
          <Button size="small" appearance="subtle" icon={<Delete24Regular />} aria-label="Delete" onClick={() => del(r.id)} /></> }]} /></Section>
    </>
  );
}

function Settings() {
  const [s, setS] = useState(null); const [ok, setOk] = useState(""); const [err, setErr] = useState("");
  useEffect(() => { api("/settings/").then(setS); }, []);
  const save = async (k, v) => { setErr(""); try { setS(await api("/settings/", { method: "PATCH", body: { [k]: v } })); setOk("Strategy updated – applies to the next incident"); } catch (x) { setErr(x.message); } };
  if (!s) return null;
  const A = [["SKILL", "Skill based"], ["LOAD", "Load based"], ["ROUND_ROBIN", "Round robin"], ["SMART", "Smart (skills + load + experience + history)"]];
  const P = [["WEIGHTED", "Weighted score (Impact × Urgency × Criticality)"], ["RULE", "Rule based (weighted + critical-service override)"]];
  return (
    <Section title="Strategies (Strategy pattern – switchable at runtime)"><Err msg={err} /><Msg msg={ok} />
      <Sel label="Technician assignment strategy" value={s.assignment_strategy} onChange={(v) => save("assignment_strategy", v)} options={A} />
      <Sel label="Priority calculation strategy" value={s.priority_strategy} onChange={(v) => save("priority_strategy", v)} options={P} /></Section>
  );
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
    deps: <Crud endpoint="/dependencies/" empty={{ service: "", depends_on: "" }}
      fields={[{ key: "service", label: "Service", type: "select", options: [["", "Choose…"], ...svcs.map((s) => [s.id, s.name])] },
        { key: "depends_on", label: "depends on", type: "select", options: [["", "Choose…"], ...svcs.map((s) => [s.id, s.name])] }]} />,
    settings: <Settings />,
  };
  return (
    <>
      <Title2 block style={{ marginBottom: 16 }}>Administration</Title2>
      <TabList selectedValue={tab} onTabSelect={(e, d) => setTab(d.value)} style={{ marginBottom: 12 }}>
        <Tab value="users">Users & technicians</Tab><Tab value="services">IT services</Tab><Tab value="categories">Categories</Tab><Tab value="deps">Dependencies</Tab><Tab value="sla">SLA policies</Tab><Tab value="settings">Strategies</Tab>
      </TabList>
      {tabs[tab]}
    </>
  );
}
