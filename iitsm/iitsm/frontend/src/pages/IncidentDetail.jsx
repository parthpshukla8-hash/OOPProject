import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, Checkbox, Link as FLink, ProgressBar, Spinner, Text, Title3 } from "@fluentui/react-components";
import { api, fmt, fmtTime } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Area, Err, Hint, KV, Mute, Msg, PBadge, Row, Section, Sel, SlaBadge, StatusBadge, Timeline, Two, Txt } from "../ui.jsx";

export default function IncidentDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [inc, setInc] = useState(null);
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const [text, setText] = useState(""); const [internal, setInternal] = useState(true);
  const [techs, setTechs] = useState([]); const [recs, setRecs] = useState([]); const [pick, setPick] = useState("");
  const [extra, setExtra] = useState({ similar: [], suggestions: [], insights: null });
  const [rating, setRating] = useState(5); const [fb, setFb] = useState("");

  const load = useCallback(async () => {
    try {
      const i = await api(`/incidents/${id}/`); setInc(i);
      if (user.role !== "EMPLOYEE") setExtra({ similar: await api(`/incidents/${id}/similar/`), suggestions: await api(`/incidents/${id}/suggestions/`), insights: await api(`/incidents/${id}/insights/`) });
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
  if (!inc) return <><Err msg={err} /><Spinner label="Loading…" /></>;

  const isAdmin = user.role === "ADMIN";
  const isAssignee = inc.assignee?.id === user.id;
  const isReporter = inc.reporter.id === user.id;
  const staff = isAdmin || isAssignee;
  const s = inc.status;

  return (
    <>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <Title3>{inc.number} · {inc.title}</Title3><PBadge v={inc.priority} /><StatusBadge v={s} /><SlaBadge v={inc.sla_status} />
      </div>
      <Err msg={err} /><Msg msg={ok} />
      {inc.duplicate_of_number && <Hint>Possible duplicate of <b>{inc.duplicate_of_number}</b>.</Hint>}
      {inc.escalation && <Err msg={`Escalated to ${inc.escalation} – incident not acknowledged within SLA.`} />}
      <Two>
        <div>
          <Section title="Details">
            <Text style={{ whiteSpace: "pre-wrap" }}>{inc.description}</Text>
            <KV rows={[
              ["Reporter", inc.reporter.name], ["Service", inc.service_name], ["Category", inc.category_name],
              ["Impact / Urgency", `${inc.impact} / ${inc.urgency} · ${inc.affected_users} user(s) · score ${inc.score}`],
              ["Technician", inc.assignee?.name || "Not yet assigned"], ["Created", fmt(inc.created_at)],
              ["Response due", <>{fmtTime(inc.response_due)} {inc.response_breached && <Badge color="danger">breached</Badge>}</>],
              ["Resolution due", <>{fmtTime(inc.resolution_due)} {inc.resolution_breached && <Badge color="danger">breached</Badge>}</>],
              inc.resolution && ["Resolution", inc.resolution], inc.closed_at && ["Closed", fmt(inc.closed_at)],
            ]} />
          </Section>

          <Section title="Actions">
            <Row style={{ alignItems: "center" }}>
              {staff && s === "ASSIGNED" && <Button appearance="primary" onClick={() => run("acknowledge", {}, "Acknowledged")}>Acknowledge</Button>}
              {staff && ["ACKNOWLEDGED", "AWAITING_INFO"].includes(s) && <Button appearance="primary" onClick={() => run("start", {}, "Investigation started")}>Start investigation</Button>}
              {isReporter && s === "RESOLVED" && <>
                <Button appearance="primary" onClick={() => run("verify", {}, "Resolution verified")}>Confirm fixed</Button>
                <Button onClick={() => run("reopen", { message: text || "Issue persists" }, "Reopened")}>Not fixed – reopen</Button></>}
              {isAdmin && !isReporter && s === "RESOLVED" && <Button appearance="primary" onClick={() => run("verify", {}, "Verified")}>Verify</Button>}
              {staff && s === "VERIFIED" && <Button appearance="primary" onClick={() => run("close", {}, "Incident closed")}>Close incident</Button>}
              {staff && s === "IN_PROGRESS" && <>
                <Button appearance="primary" onClick={() => run("resolve", { message: text }, "Marked resolved")}>Resolve with text below</Button>
                <Button onClick={() => run("request-info", { message: text }, "Info requested")}>Request info from reporter</Button></>}
              {isReporter && s === "AWAITING_INFO" && <Button appearance="primary" onClick={() => run("respond", { message: text }, "Reply sent")}>Send requested info</Button>}
            </Row>
            {(staff || isReporter) && s !== "CLOSED" && <>
              <Area label={staff ? "Resolution / message / note" : "Add information"} value={text} onChange={setText} rows={3} />
              <Row style={{ alignItems: "center" }}>
                {staff && <Checkbox checked={internal} onChange={(e, d) => setInternal(!!d.checked)} label="Internal note (hidden from reporter)" />}
                <Button onClick={() => run("comment", { text, internal: staff && internal }, "Added")}>Add {staff ? "note" : "comment"}</Button></Row></>}
            {isAdmin && ["CLASSIFIED", "ASSIGNED"].includes(s) && <Row>
              <Sel label={s === "ASSIGNED" ? "Re-assign technician" : "Assign technician"} any="Choose…" value={pick} onChange={setPick}
                options={techs.map((t) => [t.id, `${t.name} – load ${t.active_load}/${t.max_load}${t.is_available ? "" : " (away)"}`])} />
              <Button appearance="primary" disabled={!pick} onClick={() => run("assign", { technician: +pick }, "Assigned")}>Assign</Button>
              <Button onClick={() => run("assign", {}, "Auto-assign attempted")}>Auto-assign (current strategy)</Button></Row>}
            {s === "CLOSED" && <Mute>This incident is closed.</Mute>}
          </Section>

          {isReporter && ["RESOLVED", "VERIFIED", "CLOSED"].includes(s) && !inc.feedback_rating && (
            <Section title="Rate the resolution"><Row>
              <Sel label="Rating" value={rating} onChange={(v) => setRating(+v)} options={[5, 4, 3, 2, 1].map((n) => [n, `${n} / 5`])} />
              <Txt label="Comments (optional)" value={fb} onChange={setFb} />
              <Button appearance="primary" onClick={() => run("feedback", { rating, comment: fb }, "Thanks for the feedback")}>Submit</Button></Row></Section>)}
          {inc.feedback_rating && <Mute block style={{ marginBottom: 16 }}>Feedback: {inc.feedback_rating}/5 {inc.feedback_comment}</Mute>}

          <Section title="Conversation & notes">
            {!inc.comments.length && <Mute>No messages yet.</Mute>}
            {inc.comments.map((c) => <div key={c.id}><Text weight="semibold">{c.author.name}</Text> <Mute>{fmt(c.created_at)} · {c.kind.replace("_", " ").toLowerCase()}{c.internal ? " · internal" : ""}</Mute>
              <div style={{ whiteSpace: "pre-wrap" }}>{c.text}</div></div>)}
          </Section>
        </div>

        <div>
          {staff && extra.insights && <Section title="Insights">
            {extra.insights.root_cause && <Hint><b>Probable root cause:</b> upstream service <b>{extra.insights.root_cause.service}</b> already has open incident(s) {extra.insights.root_cause.incidents.join(", ")}. Consider working that incident first.</Hint>}
            {extra.insights.prediction && <div><Text weight="semibold">SLA breach risk: {Math.round(extra.insights.prediction.probability * 100)}% ({extra.insights.prediction.level})</Text>
              <ProgressBar value={extra.insights.prediction.probability} max={1} thickness="large" color={extra.insights.prediction.level === "HIGH" ? "error" : extra.insights.prediction.level === "MEDIUM" ? "warning" : "success"} />
              <Mute>Predicted {extra.insights.prediction.predicted_minutes} min vs {extra.insights.prediction.window_minutes} min target ({extra.insights.prediction.samples} historical samples)</Mute></div>}
            <div><Text weight="semibold">Blast radius</Text>
              {extra.insights.blast_radius.length ? extra.insights.blast_radius.map((b) => <div key={b.name}>• {b.name} <Mute>(criticality {b.criticality}, {b.depth === 1 ? "direct" : "indirect"})</Mute></div>) : <div><Mute>No dependent services.</Mute></div>}</div>
          </Section>}
          {isAdmin && recs.length > 0 && <Section title="Smart technician recommendation">
            {recs.map((r, n) => <div key={r.technician.id}><Text weight="semibold">{n + 1}. {r.technician.name}</Text> – {r.score} pts
              <Mute block>skill {r.breakdown.skill} · capacity {r.breakdown.capacity} · experience {r.breakdown.experience} · history {r.breakdown.history}</Mute></div>)}</Section>}
          {staff && extra.similar.length > 0 && <Section title="Related incidents">
            {extra.similar.map((x) => <div key={x.id}><Link to={`/incidents/${x.id}`}>{x.number}</Link> {x.title} <Mute>{Math.round(x.score * 100)}%</Mute></div>)}</Section>}
          {staff && extra.suggestions.length > 0 && <Section title="Suggested resolutions">
            {extra.suggestions.map((x) => <div key={x.number}><Text weight="semibold">{x.number}</Text> <Mute>({Math.round(x.score * 100)}% similar)</Mute>
              <div>{x.resolution}</div>{s === "IN_PROGRESS" && <FLink onClick={() => setText(x.resolution)}>use as resolution</FLink>}</div>)}</Section>}
          <Section title="History (audit trail)"><Timeline items={inc.history} /></Section>
        </div>
      </Two>
    </>
  );
}
