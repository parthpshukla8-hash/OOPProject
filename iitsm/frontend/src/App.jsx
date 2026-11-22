import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
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

const NAV = {
  EMPLOYEE: [["/", "Dashboard"], ["/incidents", "My incidents"], ["/new", "Report incident"], ["/notifications", "Notifications"]],
  TECHNICIAN: [["/", "Dashboard"], ["/incidents", "Assigned incidents"], ["/notifications", "Notifications"]],
  ADMIN: [["/", "Dashboard"], ["/incidents", "All incidents"], ["/new", "Report incident"], ["/reports", "Reports"],
          ["/audit", "Audit log"], ["/admin", "Administration"], ["/notifications", "Notifications"]],
};

function Shell({ children }) {
  const { user, signOut } = useAuth();
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    const load = () => api("/notifications/unread/").then((d) => setUnread(d.count)).catch(() => {});
    load(); const t = setInterval(load, 20000); return () => clearInterval(t);
  }, []);
  return (
    <div className="layout">
      <nav className="side">
        <h2>I-ITSM</h2>
        {NAV[user.role].map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="t">{label}</span>{to === "/notifications" && unread > 0 && <span className="badge P1">{unread}</span>}
          </NavLink>
        ))}
        <div className="who">{user.name}<br />{user.role.toLowerCase()}<br /><a href="#" onClick={(e) => { e.preventDefault(); signOut(); }} style={{ color: "#9fb2ff" }}>Sign out</a></div>
      </nav>
      <main className="main">{children}</main>
    </div>
  );
}

export default function App() {
  const { user, ready } = useAuth();
  if (!ready) return <p style={{ padding: 30 }}>Loading…</p>;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  const admin = user.role === "ADMIN";
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/notifications" element={<Notifications />} />
        {user.role !== "TECHNICIAN" && <Route path="/new" element={<NewIncident />} />}
        {admin && <Route path="/reports" element={<Reports />} />}
        {admin && <Route path="/audit" element={<Audit />} />}
        {admin && <Route path="/admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}
