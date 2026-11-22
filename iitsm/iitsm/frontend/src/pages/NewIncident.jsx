import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Link as FLink, Title2 } from "@fluentui/react-components";
import { api } from "../api.js";
import { Area, Err, Hint, Mute, Row, Section, Sel, Two, Txt } from "../ui.jsx";

const LEVELS = [[1, "1 – Low"], [2, "2 – Medium"], [3, "3 – High"], [4, "4 – Critical"]];

export default function NewIncident() {
  const nav = useNavigate();
  const [svcs, setSvcs] = useState([]); const [cats, setCats] = useState([]);
  const [f, setF] = useState({ title: "", description: "", service: "", category: "", impact: 2, urgency: 2, affected_users: 1 });
  const [hint, setHint] = useState(null);
  const [err, setErr] = useState("");
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));

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
    <form onSubmit={submit}>
      <Title2 block style={{ marginBottom: 16 }}>Report an incident</Title2>
      <Two>
        <Section><Err msg={err} />
          <Txt label="Title" required value={f.title} onChange={set("title")} maxLength={200} />
          <Area label="Description" value={f.description} onChange={set("description")} rows={5} />
          <Row><Sel label="Affected service" value={f.service} onChange={set("service")} options={svcs.map((s) => [s.id, s.name])} />
            <Sel label="Category" value={f.category} onChange={set("category")} any="Auto-detect" options={cats.map((c) => [c.id, c.name])} /></Row>
          <Row><Sel label="Impact" value={f.impact} onChange={set("impact")} options={LEVELS} />
            <Sel label="Urgency" value={f.urgency} onChange={set("urgency")} options={LEVELS} />
            <Txt label="Users affected" type="number" min="1" value={f.affected_users} onChange={set("affected_users")} /></Row>
          <div><Button appearance="primary" type="submit">Submit incident</Button></div>
        </Section>
        <div>
          {hint?.category && <Hint intent="info"><b>Suggested category:</b> {hint.category.name}{hint.matched.length > 0 && ` (matched: ${hint.matched.join(", ")})`}{" "}
            <FLink onClick={() => set("category")(hint.category.id)}>Use this category</FLink></Hint>}
          {hint?.duplicates.length > 0 && <Hint><b>Similar open incidents</b> – this may already be reported:
            {hint.duplicates.map((d) => <div key={d.number}>{d.number} – {d.title} ({Math.round(d.score * 100)}% match)</div>)}</Hint>}
          <Section><Mute size={300}>Priority and SLA are calculated automatically from impact × urgency × the service's business criticality.</Mute></Section>
        </div>
      </Two>
    </form>
  );
}
