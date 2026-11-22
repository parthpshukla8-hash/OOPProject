import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  Avatar, Badge, Button, FluentProvider, Spinner, Switch, Tab, TabList, Text, Title3, makeStyles, tokens,
  webDarkTheme, webLightTheme,
} from "@fluentui/react-components";
import {
  Add24Regular, Alert24Regular, DataBarVertical24Regular, History24Regular, Home24Regular, List24Regular,
  Organization24Regular, Settings24Regular, SignOut24Regular,
} from "@fluentui/react-icons";
import { api } from "./api.js";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Incidents from "./pages/Incidents.jsx";
import NewIncident from "./pages/NewIncident.jsx";
import IncidentDetail from "./pages/IncidentDetail.jsx";
import Notifications from "./pages/Notifications.jsx";
import Reports from "./pages/Reports.jsx";
import Audit from "./pages/Audit.jsx";
import Admin from "./pages/Admin.jsx";
import ServiceMap from "./pages/ServiceMap.jsx";

const NAV = {
  EMPLOYEE: [["/", "Dashboard", Home24Regular], ["/incidents", "My incidents", List24Regular], ["/new", "Report incident", Add24Regular], ["/notifications", "Notifications", Alert24Regular]],
  TECHNICIAN: [["/", "Dashboard", Home24Regular], ["/incidents", "Assigned incidents", List24Regular], ["/map", "Service map", Organization24Regular], ["/notifications", "Notifications", Alert24Regular]],
  ADMIN: [["/", "Dashboard", Home24Regular], ["/incidents", "All incidents", List24Regular], ["/new", "Report incident", Add24Regular],
          ["/map", "Service map", Organization24Regular], ["/reports", "Reports", DataBarVertical24Regular], ["/audit", "Audit log", History24Regular], ["/admin", "Administration", Settings24Regular],
          ["/notifications", "Notifications", Alert24Regular]],
};

const useS = makeStyles({
  layout: { display: "flex", minHeight: "100vh" },
  side: { width: "250px", flexShrink: 0, display: "flex", flexDirection: "column", gap: "12px", padding: "16px 8px", backgroundColor: tokens.colorNeutralBackground2, borderRight: `1px solid ${tokens.colorNeutralStroke2}`, position: "sticky", top: 0, height: "100vh", boxSizing: "border-box" },
  main: { flex: 1, padding: "24px 32px", maxWidth: "1280px", minWidth: 0 },
  who: { marginTop: "auto", display: "grid", gap: "8px", padding: "8px" },
});

function Shell({ dark, setDark, children }) {
  const s = useS();
  const { user, signOut } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    const load = () => api("/notifications/unread/").then((d) => setUnread(d.count)).catch(() => {});
    load(); const t = setInterval(load, 20000); return () => clearInterval(t);
  }, []);
  const items = NAV[user.role];
  const selected = items.map(([to]) => to).filter((to) => (to === "/" ? pathname === "/" : pathname.startsWith(to))).sort((a, b) => b.length - a.length)[0] || "/";
  return (
    <div className={s.layout}>
      <nav className={s.side}>
        <Title3 style={{ padding: "0 12px" }}>I-ITSM</Title3>
        <TabList vertical selectedValue={selected} onTabSelect={(e, d) => nav(d.value)}>
          {items.map(([to, label, Icon]) => (
            <Tab key={to} value={to} icon={<Icon />}>{label}{to === "/notifications" && unread > 0 && <> <Badge size="small" color="danger">{unread}</Badge></>}</Tab>
          ))}
        </TabList>
        <div className={s.who}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}><Avatar name={user.name} color="colorful" />
            <div><Text weight="semibold" block>{user.name}</Text><Text size={200} style={{ textTransform: "capitalize" }}>{user.role.toLowerCase()}</Text></div></div>
          <Switch label="Dark mode" checked={dark} onChange={(e, d) => setDark(d.checked)} />
          <Button icon={<SignOut24Regular />} appearance="subtle" onClick={signOut}>Sign out</Button>
        </div>
      </nav>
      <main className={s.main}>{children}</main>
    </div>
  );
}

function Routed({ dark, setDark }) {
  const { user, ready } = useAuth();
  if (!ready) return <Spinner style={{ padding: 60 }} label="Loading…" />;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  return (
    <Shell dark={dark} setDark={setDark}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/notifications" element={<Notifications />} />
        {user.role !== "TECHNICIAN" && <Route path="/new" element={<NewIncident />} />}
        {user.role !== "EMPLOYEE" && <Route path="/map" element={<ServiceMap />} />}
        {user.role === "ADMIN" && <Route path="/reports" element={<Reports />} />}
        {user.role === "ADMIN" && <Route path="/audit" element={<Audit />} />}
        {user.role === "ADMIN" && <Route path="/admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}

export default function App() {
  const [dark, setDarkState] = useState(localStorage.getItem("dark") === "1");
  const setDark = (v) => { localStorage.setItem("dark", v ? "1" : "0"); setDarkState(v); };
  return (
    <FluentProvider theme={dark ? webDarkTheme : webLightTheme} style={{ minHeight: "100vh" }}>
      <Routed dark={dark} setDark={setDark} />
    </FluentProvider>
  );
}
