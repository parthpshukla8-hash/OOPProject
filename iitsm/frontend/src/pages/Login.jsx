import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Err } from "../ui.jsx";

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "", first_name: "", last_name: "", email: "" });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try { signIn(await api(mode === "login" ? "/auth/login/" : "/auth/register/", { method: "POST", body: f })); }
    catch (x) { setErr(x.message); }
  };
  return (
    <form className="card auth" onSubmit={submit}>
      <h1>I-ITSM</h1>
      <p className="mute">Intelligent IT Service Management & Incident Resolution</p>
      <Err msg={err} />
      {mode === "register" && <div className="row"><div><label>First name</label><input value={f.first_name} onChange={set("first_name")} /></div><div><label>Last name</label><input value={f.last_name} onChange={set("last_name")} /></div></div>}
      <label>Username</label><input value={f.username} onChange={set("username")} required />
      {mode === "register" && <><label>Email</label><input type="email" value={f.email} onChange={set("email")} /></>}
      <label>Password</label><input type="password" value={f.password} onChange={set("password")} required />
      <button style={{ width: "100%", marginTop: 14 }}>{mode === "login" ? "Sign in" : "Create employee account"}</button>
      <p className="mute" style={{ textAlign: "center" }}>
        <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); }}>
          {mode === "login" ? "New employee? Register" : "Have an account? Sign in"}</a></p>
      {mode === "login" && <p className="mute">Demo: admin/admin123 · t101/tech1234 · e101/pass1234</p>}
    </form>
  );
}
