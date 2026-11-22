from django.core.management.base import BaseCommand

from itsm.factories import UserFactory
from itsm.models import Category, Service, ServiceDependency, SLAPolicy, SystemSetting, User
from itsm.services import IncidentService

CATEGORIES = {
    "Hardware": "laptop,printer,monitor,keyboard,hardware,device,battery",
    "Software": "install,software,license,update,office,excel",
    "Network": "network,wifi,vpn,internet,router,firewall,dns,connectivity",
    "Database": "database,sql,query,db,replication,deadlock",
    "Cloud": "cloud,aws,azure,kubernetes,container,instance",
    "Security": "security,phishing,malware,virus,breach,ransomware,suspicious",
    "Authentication": "login,sso,mfa,locked,access denied,permission",
    "Application": "application,app,payment,portal,website,crash,fail",
    "Storage": "storage,disk,backup,drive,quota,nas",
}
SERVICES = [("Payment Application", 5), ("Database Cluster", 5), ("Authentication / SSO", 5), ("Corporate Network & VPN", 4),
            ("Cloud Storage", 3), ("Email & Collaboration", 3), ("HR Portal", 2), ("Printing Services", 1)]
SLA = {"P1": (5, 30), "P2": (15, 120), "P3": (60, 480), "P4": (240, 1440)}
TECHS = [("t101", "Asha Rao", 8, 5, ["Application", "Database", "Cloud"]),
         ("t102", "Bilal Khan", 4, 5, ["Network", "Security", "Authentication"]),
         ("t103", "Chitra Iyer", 6, 6, ["Application", "Software", "Storage"]),
         ("t104", "Dev Malhotra", 2, 4, ["Hardware", "Network", "Storage"])]


class Command(BaseCommand):
    help = "Load demo data (idempotent)."

    def handle(self, *a, **o):
        if User.objects.filter(username="admin").exists():
            return self.stdout.write("Already seeded.")
        cats = {n: Category.objects.create(name=n, keywords=k) for n, k in CATEGORIES.items()}
        svcs = {n: Service.objects.create(name=n, business_criticality=c) for n, c in SERVICES}
        for p, (r, s) in SLA.items():
            SLAPolicy.objects.create(priority=p, response_minutes=r, resolution_minutes=s)
        SLAPolicy.objects.create(service=svcs["Payment Application"], priority="P1", response_minutes=3, resolution_minutes=20)
        SystemSetting.load()
        for a, b in (("Payment Application", "Database Cluster"), ("Payment Application", "Authentication / SSO"),
                     ("Payment Application", "Corporate Network & VPN"), ("Authentication / SSO", "Database Cluster"),
                     ("Email & Collaboration", "Authentication / SSO"), ("HR Portal", "Authentication / SSO"),
                     ("HR Portal", "Database Cluster"), ("Cloud Storage", "Corporate Network & VPN")):
            ServiceDependency.objects.create(service=svcs[a], depends_on=svcs[b])

        UserFactory.create("ADMIN", "admin", "admin123", first_name="Ira", last_name="Manager", email="admin@corp.local")
        techs = []
        for u, name, exp, load, skills in TECHS:
            first, last = name.split()
            t = UserFactory.create("TECHNICIAN", u, "tech1234", first_name=first, last_name=last, email=f"{u}@corp.local",
                                   experience_years=exp, max_load=load)
            t.skills.set([cats[s] for s in skills])
            techs.append(t)
        emps = [UserFactory.create("EMPLOYEE", u, "pass1234", first_name=f, last_name=l, email=f"{u}@corp.local")
                for u, f, l in (("e101", "Esha", "Nair"), ("e102", "Farhan", "Ali"), ("e103", "Gita", "Menon"))]

        # a few historical, closed incidents so "suggested resolution" has data to reuse
        history = [("Payment application unavailable", "Users cannot complete payment transactions, gateway timeout.",
                    "Payment Application", 4, 4, 120, "Restarted the payment gateway pods and cleared the stuck connection pool."),
                   ("VPN connection keeps dropping", "VPN disconnects every few minutes for remote staff.",
                    "Corporate Network & VPN", 2, 3, 15, "Updated VPN concentrator firmware and raised the idle timeout."),
                   ("Database queries very slow", "Reports time out, database latency high since morning.",
                    "Database Cluster", 3, 3, 30, "Rebuilt fragmented indexes and killed a runaway query holding locks.")]
        for title, desc, svc, imp, urg, users, fix in history:
            inc = IncidentService.create(emps[0], dict(title=title, description=desc, service=svcs[svc].id,
                                                       impact=imp, urgency=urg, affected_users=users))
            if inc.assignee:
                for act, msg in (("acknowledge", ""), ("start", ""), ("resolve", fix), ("verify", "")):
                    actor = emps[0] if act == "verify" else inc.assignee
                    IncidentService.perform(inc, actor, act, msg)
                IncidentService.perform(inc, inc.assignee, "close")
        self.stdout.write(self.style.SUCCESS("Seeded. Logins: admin/admin123, t101-t104/tech1234, e101-e103/pass1234"))
