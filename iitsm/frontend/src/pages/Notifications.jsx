import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../api.js";
import { Badge } from "../ui.jsx";

export default function Notifications() {
  const nav = useNavigate();
  const [tab, setTab] = useState("IN_APP");
  const [rows, setRows] = useState([]);
  useEffect(() => { api(`/notifications/?channel=${tab}`).then(setRows); if (tab === "IN_APP") api("/notifications/mark-read/", { method: "POST" }); }, [tab]);
  return (
    <>
      <h1>Notifications</h1>
      <div className="row tight" style={{ marginBottom: 12 }}>{[["IN_APP", "In-app"], ["EMAIL", "Email (simulated)"], ["SMS", "SMS (simulated)"]].map(([k, t]) =>
        <button key={k} className={tab === k ? "" : "ghost"} onClick={() => setTab(k)}>{t}</button>)}</div>
      <div className="card"><table><tbody>{rows.map((n) => (
        <tr key={n.id} className={n.incident ? "click" : ""} onClick={() => n.incident && nav(`/incidents/${n.incident}`)}>
          <td style={{ width: 150 }} className="mute">{fmt(n.created_at)}</td><td><Badge v={n.channel} cls="P3" /></td><td>{n.message}</td></tr>))}</tbody></table>
        {!rows.length && <p className="mute">No notifications.</p>}</div>
    </>
  );
}
