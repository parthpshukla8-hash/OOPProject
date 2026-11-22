export const Badge = ({ v, cls }) => <span className={`badge ${cls || v}`}>{String(v).replace("_", " ")}</span>;
export const Err = ({ msg }) => (msg ? <div className="err">{msg}</div> : null);
export const Msg = ({ msg }) => (msg ? <div className="msg">{msg}</div> : null);
export const Stat = ({ label, value }) => <div className="stat"><b>{value ?? "—"}</b><span>{label}</span></div>;
export const Bars = ({ rows }) => {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return rows.map((r) => (
    <div key={r.label} style={{ marginBottom: 8 }}>
      <div className="row tight" style={{ justifyContent: "space-between", display: "flex", fontSize: 13 }}><span>{r.label}</span><b>{r.count}</b></div>
      <div className="bar"><i style={{ width: `${(r.count / max) * 100}%` }} /></div>
    </div>
  ));
};
