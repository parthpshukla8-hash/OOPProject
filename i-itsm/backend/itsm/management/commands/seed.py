import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from itsm import services
from itsm.models import (AuditEvent, Category, Incident, IncidentStatus, Service, ServiceDependency, SlaPolicy,
                         SystemConfiguration, User)
from itsm.priority import calculate_incident_priority
from itsm.sla import apply_sla_deadlines

CATEGORIES = {
    "Hardware": "laptop device printer monitor keyboard battery screen peripheral charger",
    "Software": "install software licence update crash office excel mail calendar",
    "Network": "network wifi vpn internet connectivity router switch latency dns",
    "Database": "database sql query table replication backup deadlock reporting server",
    "Cloud": "cloud server instance virtual machine deployment container hosting",
    "Security": "security phishing malware virus suspicious breach ransomware",
    "Authentication": "login signin credential sso password locked account mfa token",
    "Application": "application portal transaction checkout payment error page",
    "Storage": "storage disk file share drive folder quota backup space upload",
    "Other": "general request question",
}

# name: (description, keywords, criticality, default category)
SERVICES = {
    "Payment Application": ("Customer and internal payment processing", "payment transaction checkout card refund gateway", 5, "Application"),
    "Core Database": ("Shared relational databases", "database sql query replication deadlock server", 4, "Database"),
    "Single Sign-On": ("Company-wide authentication", "login signin sso password credential mfa locked account token", 5, "Authentication"),
    "Corporate Network": ("Office network, Wi-Fi and VPN", "network wifi vpn internet connectivity router", 4, "Network"),
    "Cloud Storage": ("Shared files and backups", "storage file share drive folder upload quota", 3, "Storage"),
    "Email & Calendar": ("Mail, calendar and meetings", "email mailbox calendar meeting invite inbox", 3, "Software"),
    "HR Portal": ("Leave, payroll and HR records", "hr portal leave payroll payslip", 2, "Application"),
    "Laptops & Devices": ("Employee laptops and peripherals", "laptop device battery screen keyboard printer", 2, "Hardware"),
    "General IT": ("Anything that does not fit elsewhere", "", 1, "Other"),
}
DEPENDENCIES = [("Payment Application", "Core Database"), ("Payment Application", "Single Sign-On"),
                ("Payment Application", "Corporate Network"), ("HR Portal", "Core Database"),
                ("HR Portal", "Single Sign-On"), ("Cloud Storage", "Corporate Network"),
                ("Email & Calendar", "Single Sign-On"), ("Email & Calendar", "Corporate Network"),
                ("Single Sign-On", "Core Database")]

HISTORY = {
    "Payment Application": [
        ("Payment application unavailable", "Users are unable to complete transactions. The payment application shows a gateway error and checkout is down.", "Restarted the payment gateway service and cleared the stuck connection pool. Transactions resumed."),
        ("Card payments failing at checkout", "Card transactions fail with a declined error for every customer, even with valid cards.", "Renewed the expired gateway API certificate and redeployed the payment service."),
        ("Refund requests stuck in pending", "Refunds submitted from the payment portal stay pending and never reach the customer.", "Replayed the failed refund queue and increased the worker timeout.")],
    "Core Database": [
        ("Database query timeouts on reporting server", "Reports time out. Queries on the reporting database run for minutes and then fail.", "Added a missing index on the transactions table and killed a long running blocking query."),
        ("Database replication lag", "The replica database is minutes behind the primary and reports show stale data.", "Restarted the replication process and freed disk space on the replica."),
        ("Deadlock errors in nightly batch", "The nightly batch job fails with deadlock errors on the orders tables.", "Reordered the batch update statements and reduced the batch size.")],
    "Single Sign-On": [
        ("Cannot login to SSO", "Several users cannot sign in. The single sign-on page rejects valid credentials.", "Unlocked the affected accounts and restarted the identity provider node that held stale sessions."),
        ("MFA codes not accepted", "Authenticator codes are rejected at login even when entered correctly.", "Resynchronised the time on the identity server so one-time codes validate again."),
        ("Password reset email never arrives", "The password reset link is not delivered after requesting a reset.", "Released the reset emails stuck in the mail queue and fixed the sender configuration.")],
    "Corporate Network": [
        ("VPN keeps disconnecting", "The VPN drops every few minutes for remote employees and they lose their sessions.", "Raised the VPN session timeout and replaced a faulty gateway interface."),
        ("Wi-Fi very slow on second floor", "Wi-Fi on the second floor is extremely slow and drops connections.", "Replaced a failing access point and rebalanced the wireless channels."),
        ("Office internet is down", "No internet access across the whole office. Websites do not load.", "Restarted the edge router and failed over to the backup internet link.")],
    "Cloud Storage": [
        ("Cannot upload files to shared drive", "Uploads to the shared drive fail with a quota exceeded message.", "Increased the team storage quota and archived old files."),
        ("Shared folder not accessible", "The team folder shows access denied for people who had access yesterday.", "Restored the folder permissions from the last backup of the access list.")],
    "Email & Calendar": [
        ("Email not syncing on phone", "Mail stopped syncing on mobile devices and the inbox is out of date.", "Removed and re-added the mail profile and cleared the sync cache on the mail server."),
        ("Calendar invites not delivered", "Meeting invites sent to external guests are never delivered.", "Fixed the outbound mail relay rule that blocked calendar attachments.")],
    "HR Portal": [
        ("HR portal payslip page error", "The payslip page shows an error instead of the monthly payslip.", "Fixed a broken report template and regenerated the payslips."),
        ("Leave request cannot be submitted", "Submitting a leave request fails with a validation error.", "Corrected the leave policy configuration for the new financial year.")],
    "Laptops & Devices": [
        ("Laptop battery not charging", "The laptop battery stays at the same level while plugged in and does not charge.", "Replaced the faulty charger and updated the battery firmware."),
        ("Laptop screen flickering", "The laptop display flickers and shows lines after waking from sleep.", "Updated the graphics driver and replaced the display cable."),
        ("Printer offline on third floor", "The shared printer shows offline and print jobs are stuck.", "Reinstalled the printer driver and reset the print spooler.")],
    "General IT": [
        ("Need design software installed", "Please install a licensed design tool on my machine.", "Installed the requested software and assigned a licence.")],
}
SUFFIXES = ["Started this morning.", "Affects my whole team.", "Happened again after lunch.", "Blocking my work.", ""]

TECHNICIANS = [  # username, first, last, skills, years, lead
    ("t101", "Arjun", "Mehta", ["Database", "Cloud", "Storage"], 8, "t104"),
    ("t102", "Sana", "Iqbal", ["Network", "Security", "Authentication"], 5, "t104"),
    ("t103", "Rohit", "Verma", ["Application", "Software", "Hardware"], 6, "t104"),
    ("t104", "Meera", "Nair", ["Application", "Authentication", "Hardware", "Database"], 10, None),
]
EMPLOYEES = [("e101", "Kavya", "Reddy"), ("e102", "Imran", "Shaikh"), ("e103", "Neha", "Joshi"), ("e104", "Dev", "Patel")]


class Command(BaseCommand):
    help = "Load demo users, services, SLA policies, dependencies, history and a few open incidents."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("Data already present. Delete db.sqlite3 and migrate again to reseed.")
            return
        rng = random.Random(7)
        SystemConfiguration.current()
        categories = {name: Category.objects.create(name=name, description=name, keywords=words)
                      for name, words in CATEGORIES.items()}
        svc = {}
        for name, (description, keywords, criticality, category) in SERVICES.items():
            svc[name] = Service.objects.create(name=name, description=description, keywords=keywords,
                                               business_criticality=criticality, default_category=categories[category])
        for service, depends_on in DEPENDENCIES:
            ServiceDependency.objects.create(service=svc[service], depends_on=svc[depends_on])
        for priority, response, resolution in (("P1", 5, 30), ("P2", 15, 120), ("P3", 60, 480), ("P4", 240, 1440)):
            SlaPolicy.objects.create(priority=priority, response_minutes=response, resolution_minutes=resolution)
        SlaPolicy.objects.create(priority="P1", service=svc["Payment Application"], response_minutes=3, resolution_minutes=20)
        SlaPolicy.objects.create(priority="P2", service=svc["Payment Application"], response_minutes=10, resolution_minutes=90)

        User.objects.create_user("admin", password="admin123", first_name="Priya", last_name="Raman",
                                 email="admin@example.org", role=User.Role.ADMINISTRATOR, is_staff=True, is_superuser=True)
        User.objects.create_user("manager", password="manager123", first_name="Vikram", last_name="Rao",
                                 email="manager@example.org", role=User.Role.ADMINISTRATOR, is_staff=True,
                                 is_it_manager=True)
        technicians = {}
        for username, first, last, skills, years, _ in TECHNICIANS:
            technician = User.objects.create_user(username, password="tech1234", first_name=first, last_name=last,
                                                  email=f"{username}@example.org", role=User.Role.TECHNICIAN,
                                                  experience_years=years)
            technician.skills.set([categories[s] for s in skills])
            technicians[username] = technician
        for username, _, _, _, _, lead in TECHNICIANS:
            if lead:
                technicians[username].team_lead = technicians[lead]
                technicians[username].save(update_fields=["team_lead"])
        employees = [User.objects.create_user(u, password="pass1234", first_name=f, last_name=l,
                                              email=f"{u}@example.org", role=User.Role.EMPLOYEE)
                     for u, f, l in EMPLOYEES]

        self._history(rng, svc, categories, list(technicians.values()), employees)
        self._open_incidents(employees, svc)
        self.stdout.write(self.style.SUCCESS(
            "Seeded. Logins: admin/admin123, manager/manager123, t101-t104/tech1234, e101-e104/pass1234"))

    def _history(self, rng, svc, categories, technicians, employees):
        now = timezone.now()
        entries = [(name, t) for name, items in HISTORY.items() for t in items]
        for n in range(56):
            service_name, (title, description, resolution) = entries[n % len(entries)]
            service = svc[service_name]
            category = service.default_category
            skilled = [t for t in technicians if category in t.skills.all()] or technicians
            technician, reporter = rng.choice(skilled), rng.choice(employees)
            impact, urgency = rng.choice([2, 2, 3, 3, 4]), rng.choice([1, 2, 3, 3, 4])
            users = rng.choice([1, 3, 8, 25, 120])
            result = calculate_incident_priority(impact, urgency, service, users)
            created = now - timedelta(days=rng.uniform(1, 30), hours=rng.uniform(0, 8))
            incident = Incident(reporter=reporter, assignee=technician, title=title,
                                description=f"{description} {rng.choice(SUFFIXES)}".strip(), service=service,
                                category=category, impact=impact, urgency=urgency, affected_users=users,
                                priority=result.priority, priority_score=result.score,
                                priority_rationale=list(result.rationale), resolution=resolution)
            incident.save()
            incident.created_at = created
            policy = apply_sla_deadlines(incident, created)
            acknowledged = created + timedelta(minutes=rng.uniform(1, policy.response_minutes * 1.3))
            resolved = acknowledged + timedelta(minutes=rng.uniform(policy.resolution_minutes * 0.2,
                                                                    policy.resolution_minutes * 1.25))
            final = rng.choice([IncidentStatus.CLOSED] * 6 + [IncidentStatus.VERIFIED, IncidentStatus.RESOLVED])
            Incident.objects.filter(pk=incident.pk).update(
                created_at=created, status=final, acknowledged_at=acknowledged, resolved_at=resolved,
                verified_at=resolved + timedelta(minutes=20) if final != IncidentStatus.RESOLVED else None,
                closed_at=resolved + timedelta(minutes=40) if final == IncidentStatus.CLOSED else None,
                response_due_at=incident.response_due_at, resolution_due_at=incident.resolution_due_at,
                response_breached=acknowledged > incident.response_due_at,
                resolution_breached=resolved > incident.resolution_due_at,
                feedback_rating=rng.choice([3, 4, 4, 5, 5]) if final == IncidentStatus.CLOSED else None)
            for action, moment, actor, prev, new, text in (
                    ("IncidentReported", created, reporter, "", "NEW", f"{incident.code} reported by {reporter.display_name}: {title}"),
                    ("TechnicianAssigned", created + timedelta(seconds=30), None, "CLASSIFIED", "ASSIGNED", f"Assigned to {technician.display_name}."),
                    ("IncidentResolved", resolved, technician, "IN_PROGRESS", "RESOLVED", f"Resolved: {resolution}")):
                event = AuditEvent.objects.create(incident=incident, actor=actor, action=action, previous_state=prev,
                                                  new_state=new, description=text)
                AuditEvent.objects.filter(pk=event.pk).update(created_at=moment)

    def _open_incidents(self, employees, svc):
        e101, e102, e103, _ = employees
        services.create_incident(e103, "Cannot sign in to single sign-on", "Since this morning the SSO page rejects my password and says my account is locked.",
                                 impact=2, urgency=3, affected_users=1, service_id=svc["Single Sign-On"].pk)
        services.create_incident(e101, "Wi-Fi keeps dropping in meeting rooms", "The wireless network disconnects every few minutes on the third floor.",
                                 impact=2, urgency=2, affected_users=12, service_id=svc["Corporate Network"].pk)
        services.create_incident(e102, "Laptop battery not charging", "My laptop stays at 20 percent even when plugged in.",
                                 impact=1, urgency=2, affected_users=1)
