import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmt, fmtTime } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Badge, Err, Msg } from "../ui.jsx";

export default function IncidentDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [inc, setInc] = useState(null);
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const [text, setText] = useState(""); const [internal, setInternal] = useState(true);
  const [techs, setTechs] = useState([]); const [recs, setRecs] = useState([]); const [pick, setPick] = useState("");
  const [extra, setExtra] = useState({ similar: [], suggestions: [] });
  const [rating, setRating] = useState(5); const [fb, setFb] = useState("");

  const load = useCallback(async () => {
    try {
      const i = await api(`/incidents/${id}/`); setInc(i);
      if (user.role !== "EMPLOYEE") setExtra({ similar: await api(`/incidents/${id}/similar/`), suggestions: await api(`/incidents/${id}/suggestions/`) });
      if (user.role === "ADMIN" && ["CLASSIFIED", "ASSIGNED"].includes(i.status)) {
        setTechs(await api("/technicians/"));
        setRecs(await api(`/incidents/${id}/recommendations/`).catch(() => []));
      }
    } catch (x) { setErr(x.message); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const run = async (path, body = {}, msg = "Done") => {
    setErr(""); setOk("");
    try { await api(`/incidents/${id}/${path}/`, { method: "POST", body }); setOk(msg); setText(""); await load(); }
    catch (x) { setErr(x.message); }
  };
  if (!inc) return <><Err msg={err} /><p>Loading…</p></>;

  const isAdmin = user.role === "ADMIN";
  const isAssignee = inc.assignee?.id === user.id;
  const isReporter = inc.reporter.id === user.id;
  const staff = isAdmin || isAssignee;
  const s = inc.status;

  return (
    <>
      <h1>{inc.number} · {inc.title} <Badge v={inc.priority} /> <Badge v={inc.sla_status} /></h1>
      <Err msg={err} /><Msg msg={ok} />
      {inc.duplicate_of_number && <div className="hint">Possible duplicate of <b>{inc.duplicate_of_number}</b>.</div>}
      {inc.escalation && <div className="err">Escalated to {inc.escalation} – incident not acknowledged within SLA.</div>}
      <div className="two"><div>
        <div className="card"><h3>Details</h3><p style={{ whiteSpace: "pre-wrap" }}>{inc.description}</p>
          <div className="kv"><span>Status</span><span><b>{s.replace("_", " ")}</b></span><span>Reporter</span><span>{inc.reporter.name}</span>
            <span>Service</span><span>{inc.service_name}</span><span>Category</span><span>{inc.category_name}</span>
            <span>Impact / Urgency</span><span>{inc.impact} / {inc.urgency} · {inc.affected_users} user(s) · score {inc.score}</span>
            <span>Technician</span><span>{inc.assignee?.name || "Not yet assigned"}</span>
            <span>Created</span><span>{fmt(inc.created_at)}</span>
            <span>Response due</span><span>{fmtTime(inc.response_due)} {inc.response_breached && <Badge v="BREACHED" />}</span>
            <span>Resolution due</span><span>{fmtTime(inc.resolution_due)} {inc.resolution_breached && <Badge v="BREACHED" />}</span>
            {inc.resolution && <><span>Resolution</span><span style={{ whiteSpace: "pre-wrap" }}>{inc.resolution}</span></>}
            {inc.closed_at && <><span>Closed</span><span>{fmt(inc.closed_at)}</span></>}</div></div>

        <div className="card"><h3>Actions</h3>
          <div className="row tight">
            {staff && s === "ASSIGNED" && <button onClick={() => run("acknowledge", {}, "Acknowledged")}>Acknowledge</button>}
            {staff && ["ACKNOWLEDGED", "AWAITING_INFO"].includes(s) && <button onClick={() => run("start", {}, "Investigation started")}>Start investigation</button>}
            {isReporter && s === "RESOLVED" && <><button className="ok" onClick={() => run("verify", {}, "Resolution verified")}>Confirm fixed</button>
              <button className="danger" onClick={() => run("reopen", { message: text || "Issue persists" }, "Reopened")}>Not fixed – reopen</button></>}
            {isAdmin && !isReporter && s === "RESOLVED" && <button className="ok" onClick={() => run("verify", {}, "Verified")}>Verify</button>}
            {staff && s === "VERIFIED" && <button className="ok" onClick={() => run("close", {}, "Incident closed")}>Close incident</button>}
          </div>
          {staff && s === "IN_PROGRESS" && <><label>Resolution details / info request (use the box below)</label>
            <div className="row tight"><button onClick={() => run("resolve", { message: text }, "Marked resolved")}>Resolve with this text</button>
              <button className="ghost" onClick={() => run("request-info", { message: text }, "Info requested")}>Request info from reporter</button></div></>}
          {isReporter && s === "AWAITING_INFO" && <div className="row tight"><button onClick={() => run("respond", { message: text }, "Reply sent")}>Send requested info</button></div>}
          {(staff || isReporter) && s !== "CLOSED" && <><label>{staff ? "Message / note" : "Add information"}</label><textarea value={text} onChange={(e) => setText(e.target.value)} />
            <div className="row tight">{staff && <label style={{ margin: 0 }}><input type="checkbox" style={{ width: "auto" }} checked={internal} onChange={(e) => setInternal(e.target.checked)} /> internal note (hidden from reporter)</label>}
              <button className="ghost" onClick={() => run("comment", { text, internal: staff && internal }, "Added")}>Add {staff ? "note" : "comment"}</button></div></>}
          {isAdmin && ["CLASSIFIED", "ASSIGNED"].includes(s) && <div style={{ marginTop: 12 }}><label>Assign technician ({s === "ASSIGNED" ? "re-assign" : "manual or automatic"})</label>
            <div className="row tight"><select value={pick} onChange={(e) => setPick(e.target.value)} style={{ width: 280 }}><option value="">Choose…</option>
              {techs.map((t) => <option key={t.id} value={t.id}>{t.name} – load {t.active_load}/{t.max_load}{t.is_available ? "" : " (away)"}</option>)}</select>
              <button disabled={!pick} onClick={() => run("assign", { technician: +pick }, "Assigned")}>Assign</button>
              <button className="ghost" onClick={() => run("assign", {}, "Auto-assign attempted")}>Auto-assign (current strategy)</button></div></div>}
          {s === "CLOSED" && <p className="mute">This incident is closed.</p>}</div>

        {isReporter && ["RESOLVED", "VERIFIED", "CLOSED"].includes(s) && !inc.feedback_rating && <div className="card"><h3>Rate the resolution</h3>
          <div className="row tight"><select value={rating} onChange={(e) => setRating(+e.target.value)} style={{ width: 90 }}>{[5, 4, 3, 2, 1].map((n) => <option key={n}>{n}</option>)}</select>
            <input placeholder="Comments (optional)" value={fb} onChange={(e) => setFb(e.target.value)} style={{ width: 300 }} />
            <button onClick={() => run("feedback", { rating, comment: fb }, "Thanks for the feedback")}>Submit</button></div></div>}
        {inc.feedback_rating && <p className="mute">Feedback: {inc.feedback_rating}/5 {inc.feedback_comment}</p>}

        <div className="card"><h3>Conversation & notes</h3>{!inc.comments.length && <p className="mute">No messages yet.</p>}
          {inc.comments.map((c) => <div key={c.id} style={{ marginBottom: 10 }}><b>{c.author.name}</b> <span className="mute">{fmt(c.created_at)} · {c.kind.replace("_", " ").toLowerCase()}{c.internal ? " · internal" : ""}</span><div style={{ whiteSpace: "pre-wrap" }}>{c.text}</div></div>)}</div>
      </div>

      <div>
        {isAdmin && recs.length > 0 && <div className="card"><h3>Smart technician recommendation</h3>
          {recs.map((r, n) => <div key={r.technician.id} style={{ marginBottom: 8 }}><b>{n + 1}. {r.technician.name}</b> – {r.score} pts
            <div className="mute">skill {r.breakdown.skill} · capacity {r.breakdown.capacity} · experience {r.breakdown.experience} · history {r.breakdown.history}</div></div>)}</div>}
        {staff && extra.similar.length > 0 && <div className="card"><h3>Related incidents</h3>{extra.similar.map((x) => <div key={x.id}><Link to={`/incidents/${x.id}`}>{x.number}</Link> {x.title} <span className="mute">{Math.round(x.score * 100)}%</span></div>)}</div>}
        {staff && extra.suggestions.length > 0 && <div className="card"><h3>Suggested resolutions</h3>{extra.suggestions.map((x) => <div key={x.number} style={{ marginBottom: 8 }}><b>{x.number}</b> <span className="mute">({Math.round(x.score * 100)}% similar)</span><div>{x.resolution}</div>
          {s === "IN_PROGRESS" && <a href="#" onClick={(e) => { e.preventDefault(); setText(x.resolution); }}>use as resolution</a>}</div>)}</div>}
        <div className="card"><h3>History (audit trail)</h3><div className="tl">{inc.history.map((h) => <div key={h.id}><small>{fmt(h.timestamp)} · {h.user}</small>{h.description}</div>)}</div></div>
      </div></div>
    </>
  );
}
