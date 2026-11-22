import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Tab, TabList, Title2 } from "@fluentui/react-components";
import { api, fmt } from "../api.js";
import { ChannelBadge, DTable, Section } from "../ui.jsx";

export default function Notifications() {
  const nav = useNavigate();
  const [tab, setTab] = useState("IN_APP");
  const [rows, setRows] = useState([]);
  useEffect(() => { api(`/notifications/?channel=${tab}`).then(setRows); if (tab === "IN_APP") api("/notifications/mark-read/", { method: "POST" }); }, [tab]);
  return (
    <>
      <Title2 block style={{ marginBottom: 16 }}>Notifications</Title2>
      <TabList selectedValue={tab} onTabSelect={(e, d) => setTab(d.value)} style={{ marginBottom: 12 }}>
        <Tab value="IN_APP">In-app</Tab><Tab value="EMAIL">Email (simulated)</Tab><Tab value="SMS">SMS (simulated)</Tab>
      </TabList>
      <Section><DTable rows={rows} empty="No notifications." onRow={(n) => n.incident && nav(`/incidents/${n.incident}`)} cols={[
        { h: "When", render: (n) => fmt(n.created_at) }, { h: "Channel", render: (n) => <ChannelBadge v={n.channel} /> }, { h: "Message", render: (n) => n.message }]} /></Section>
    </>
  );
}
