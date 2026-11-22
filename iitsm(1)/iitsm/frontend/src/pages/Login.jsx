import { useState } from "react";
import { Button, Card, Field, Input, Title2 } from "@fluentui/react-components";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Err, Mute, Row } from "../ui.jsx";

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "", first_name: "", last_name: "", email: "" });
  const [err, setErr] = useState("");
  const set = (k) => (e, d) => setF({ ...f, [k]: d.value });
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try { signIn(await api(mode === "login" ? "/auth/login/" : "/auth/register/", { method: "POST", body: f })); }
    catch (x) { setErr(x.message); }
  };
  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 16 }}>
      <Card style={{ width: 400, padding: 24 }}>
        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <Title2>I-ITSM</Title2>
          <Mute>Intelligent IT Service Management & Incident Resolution</Mute>
          <Err msg={err} />
          {mode === "register" && <Row><Field label="First name" style={{ flex: 1 }}><Input value={f.first_name} onChange={set("first_name")} /></Field>
            <Field label="Last name" style={{ flex: 1 }}><Input value={f.last_name} onChange={set("last_name")} /></Field></Row>}
          <Field label="Username" required><Input value={f.username} onChange={set("username")} /></Field>
          {mode === "register" && <Field label="Email"><Input type="email" value={f.email} onChange={set("email")} /></Field>}
          <Field label="Password" required><Input type="password" value={f.password} onChange={set("password")} /></Field>
          <Button appearance="primary" type="submit">{mode === "login" ? "Sign in" : "Create employee account"}</Button>
          <Button appearance="transparent" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "New employee? Register" : "Have an account? Sign in"}</Button>
          {mode === "login" && <Mute>Demo: admin/admin123 · t101/tech1234 · e101/pass1234</Mute>}
        </form>
      </Card>
    </div>
  );
}
