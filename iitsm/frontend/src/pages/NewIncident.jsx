import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Err } from "../ui.jsx";

const LEVELS = [[1, "1 – Low"], [2, "2 – Medium"], [3, "3 – High"], [4, "4 – Critical"]];

export default function NewIncident() {
  const nav = useNavigate();
  const [svcs, setSvcs] = useState([]); const [cats, setCats] = useState([]);
  const [f, setF] = useState({ title: "", description: "", service: "", category: "", impact: 2, urgency: 2, affected_users: 1 });
  const [hint, setHint] = useState(null);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => { api("/services/").then((s) => { setSvcs(s); setF((x) => ({ ...x, service: s[0]?.id || "" })); }); api("/categories/").then(setCats); }, []);
  useEffect(() => {          // live intelligent hints: auto-category + duplicate detection
    if (f.title.length + f.description.length < 8) { setHint(null); return; }
    const t = setTimeout(() => api("/incidents/suggest/", { method: "POST", body: { title: f.title, description: f.description, service: f.service } }).then(setHint).catch(() => {}), 500);
    return () => clearTimeout(t);
  }, [f.title, f.description, f.service]);

  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      const body = { ...f, impact: +f.impact, urgency: +f.urgency, affected_users: +f.affected_users, service: +f.service, category: f.category ? +f.category : null };
      const inc = await api("/incidents/", { method: "POST", body });
      nav(`/incidents/${inc.id}`);
    } catch (x) { setErr(x.message); }
  };
  return (
    <form onSubmit={submit}><h1>Report an incident</h1>
      <div className="two"><div className="card"><Err msg={err} />
        <label>Title</label><input value={f.title} onChange={set("title")} required maxLength={200} />
        <label>Description</label><textarea value={f.description} onChange={set("description")} required />
        <div className="row"><div><label>Affected service</label><select value={f.service} onChange={set("service")}>{svcs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <div><label>Category (leave blank to auto-detect)</label><select value={f.category} onChange={set("category")}><option value="">Auto-detect</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div></div>
        <div className="row"><div><label>Impact</label><select value={f.impact} onChange={set("impact")}>{LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
          <div><label>Urgency</label><select value={f.urgency} onChange={set("urgency")}>{LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
          <div><label>Users affected</label><input type="number" min="1" value={f.affected_users} onChange={set("affected_users")} /></div></div>
        <button style={{ marginTop: 14 }}>Submit incident</button></div>
        <div>{hint?.category && <div className="hint"><b>Suggested category:</b> {hint.category.name}{hint.matched.length > 0 && <span className="mute"> (matched: {hint.matched.join(", ")})</span>}
          <div><a href="#" onClick={(e) => { e.preventDefault(); setF({ ...f, category: hint.category.id }); }}>Use this category</a></div></div>}
          {hint?.duplicates.length > 0 && <div className="hint"><b>Similar open incidents</b> – this may already be reported:
            {hint.duplicates.map((d) => <div key={d.number}>{d.number} – {d.title} <span className="mute">({Math.round(d.score * 100)}% match)</span></div>)}</div>}
          <div className="card mute">Priority and SLA are calculated automatically from impact × urgency × the service's business criticality.</div></div></div>
    </form>
  );
}
