"""Run with:  python manage.py test itsm -v 2"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from . import insights, sla
from .assignment import LoadBased, RoundRobin, SkillBased, SmartRecommendation, eligible_technicians
from .exceptions import InvalidStateTransition, WorkloadExceeded
from .factories import UserFactory
from .lifecycle import transition
from .models import AuditLog, Category, Incident, Notification, Service, ServiceDependency, SLAPolicy, technician_pool
from .priority import RuleBasedPriority, WeightedScorePriority


class Base(TestCase):
    def setUp(self):
        self.app = Category.objects.create(name="Application", keywords="payment,app,fail")
        self.net = Category.objects.create(name="Network", keywords="vpn,wifi,network")
        self.pay = Service.objects.create(name="Payment", business_criticality=5)
        self.prn = Service.objects.create(name="Printing", business_criticality=1)
        for p, (r, s) in {"P1": (5, 30), "P2": (15, 120), "P3": (60, 480), "P4": (240, 1440)}.items():
            SLAPolicy.objects.create(priority=p, response_minutes=r, resolution_minutes=s)
        self.admin = UserFactory.create("ADMIN", "admin", "admin123")
        self.t1 = UserFactory.create("TECHNICIAN", "t1", "tech1234", experience_years=8, max_load=2)
        self.t1.skills.set([self.app])
        self.t2 = UserFactory.create("TECHNICIAN", "t2", "tech1234", experience_years=1, max_load=2)
        self.t2.skills.set([self.net])
        self.e1 = UserFactory.create("EMPLOYEE", "e1", "pass1234")
        self.e2 = UserFactory.create("EMPLOYEE", "e2", "pass1234")
        self.c = APIClient()

    def as_(self, user):
        self.c.force_authenticate(user)
        return self.c

    def report(self, user, **kw):
        data = dict(title="Payment application unavailable", description="Users unable to complete payment transactions",
                    service=self.pay.id, impact=4, urgency=4, affected_users=150)
        data.update(kw)
        return self.as_(user).post("/api/incidents/", data, format="json")

    def act(self, user, inc_id, name, **body):
        return self.as_(user).post(f"/api/incidents/{inc_id}/{name}/", body, format="json")

    def raw_incident(self, **kw):
        d = dict(title="x", description="y", reporter=self.e1, category=self.app, service=self.pay)
        d.update(kw)
        return Incident.objects.create(**d)


class AuthTests(Base):
    def test_01_register_login_and_invalid_login(self):
        c = APIClient()
        r = c.post("/api/auth/register/", {"username": "newbie", "password": "secret12"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["user"]["role"], "EMPLOYEE")             # self-registration can never create staff
        self.assertEqual(c.post("/api/auth/login/", {"username": "newbie", "password": "secret12"}, format="json").status_code, 200)
        bad = c.post("/api/auth/login/", {"username": "newbie", "password": "wrong"}, format="json")
        self.assertEqual((bad.status_code, bad.data["code"]), (401, "invalid_login"))

    def test_02_unauthenticated_access_rejected(self):
        self.assertEqual(APIClient().get("/api/incidents/").status_code, 401)

    def test_03_short_password_rejected(self):
        r = APIClient().post("/api/auth/register/", {"username": "x1", "password": "123"}, format="json")
        self.assertEqual(r.status_code, 400)


class PriorityAndLifecycleTests(Base):
    def test_04_priority_boundaries(self):
        w = WeightedScorePriority()
        self.assertEqual(w.calculate(4, 4, 5, 1), (80, "P1"))
        self.assertEqual(w.calculate(4, 3, 4, 1)[1], "P1")       # 48 boundary
        self.assertEqual(w.calculate(4, 3, 2, 1)[1], "P2")       # 24 boundary
        self.assertEqual(w.calculate(2, 2, 2, 1)[1], "P3")       # 8 boundary
        self.assertEqual(w.calculate(1, 1, 7, 1)[1], "P4")       # 7 just below
        self.assertEqual(w.calculate(3, 2, 4, 100)[1], "P2")     # 24 x 1.5 user multiplier

    def test_05_rule_based_overrides_for_critical_service(self):
        self.assertEqual(WeightedScorePriority().calculate(3, 1, 5, 1)[1], "P3")
        self.assertEqual(RuleBasedPriority().calculate(3, 1, 5, 1)[1], "P1")

    def test_06_state_machine_blocks_new_to_closed(self):
        inc = self.raw_incident()
        with self.assertRaises(InvalidStateTransition):
            transition(inc, "CLOSED")

    def test_07_cannot_assign_state_without_technician(self):
        inc = self.raw_incident(status="CLASSIFIED")
        with self.assertRaises(InvalidStateTransition):
            transition(inc, "ASSIGNED")

    def test_08_close_requires_verification_via_api(self):
        iid = self.report(self.e1).data["id"]
        for a, body in (("acknowledge", {}), ("start", {}), ("resolve", {"message": "Restarted"})):
            self.assertEqual(self.act(self.t1, iid, a, **body).status_code, 200)
        r = self.act(self.admin, iid, "close")
        self.assertEqual((r.status_code, r.data["code"]), (409, "invalid_state_transition"))

    def test_09_full_lifecycle_and_audit_trail(self):
        r = self.report(self.e1)
        self.assertEqual(r.status_code, 201)
        iid = r.data["id"]
        self.assertEqual((r.data["priority"], r.data["status"], r.data["assignee"]["username"]), ("P1", "ASSIGNED", "t1"))
        self.assertIsNotNone(r.data["response_due"])
        self.act(self.t1, iid, "acknowledge")
        self.act(self.t1, iid, "start")
        self.assertEqual(self.act(self.t1, iid, "request-info", message="Which region?").data["status"], "AWAITING_INFO")
        self.assertEqual(self.act(self.e1, iid, "respond", message="All regions").data["status"], "IN_PROGRESS")
        self.act(self.t1, iid, "resolve", message="Restarted gateway")
        self.act(self.e1, iid, "verify")
        final = self.act(self.t1, iid, "close")
        self.assertEqual(final.data["status"], "CLOSED")
        actions = list(AuditLog.objects.filter(incident_id=iid).values_list("action", flat=True))
        for a in ("INCIDENT_CREATED", "PRIORITY_CALCULATED", "ASSIGNED", "STATUS_CHANGED"):
            self.assertIn(a, actions)
        self.assertGreaterEqual(len(actions), 10)
        self.assertFalse(final.data["response_breached"])

    def test_10_resolve_requires_resolution_text(self):
        iid = self.report(self.e1).data["id"]
        self.act(self.t1, iid, "acknowledge")
        self.act(self.t1, iid, "start")
        self.assertEqual(self.act(self.t1, iid, "resolve").status_code, 400)

    def test_11_invalid_input_rejected(self):
        self.assertEqual(self.report(self.e1, impact=9).status_code, 400)
        self.assertEqual(self.report(self.e1, title="").status_code, 400)
        self.assertEqual(self.report(self.e1, affected_users=0).status_code, 400)


class AuthorizationTests(Base):
    def test_12_employee_sees_only_own_incidents(self):
        iid = self.report(self.e1).data["id"]
        self.assertEqual(self.as_(self.e2).get(f"/api/incidents/{iid}/").status_code, 404)
        self.assertEqual(len(self.as_(self.e2).get("/api/incidents/").data), 0)
        self.assertEqual(len(self.as_(self.t2).get("/api/incidents/").data), 0)        # not assigned to t2

    def test_13_role_restrictions(self):
        iid = self.report(self.e1).data["id"]
        self.assertEqual(self.act(self.e1, iid, "assign").status_code, 403)
        self.assertEqual(self.act(self.e1, iid, "acknowledge").status_code, 403)
        self.assertEqual(self.as_(self.e1).get("/api/reports/").status_code, 403)
        self.assertEqual(self.as_(self.t1).get("/api/audit/").status_code, 403)
        self.assertEqual(self.as_(self.e1).post("/api/users/", {"username": "z", "password": "secret12"}, format="json").status_code, 403)
        self.assertEqual(self.as_(self.admin).get("/api/reports/").status_code, 200)


class AssignmentTests(Base):
    def probe(self):
        return Incident(category=self.app, service=self.pay)

    def test_14_strategies_pick_expected_technician(self):
        self.raw_incident(assignee=self.t1, status="IN_PROGRESS")        # t1 carries load 1
        pool = eligible_technicians()
        self.assertEqual(LoadBased().pick(self.probe(), pool).username, "t2")
        self.assertEqual(SkillBased().pick(self.probe(), pool).username, "t1")
        self.t1.last_assigned_at = timezone.now()
        self.t1.save()
        self.assertEqual(RoundRobin().pick(self.probe(), eligible_technicians()).username, "t2")
        ranked = SmartRecommendation().rank(self.probe(), eligible_technicians())
        self.assertEqual(ranked[0]["technician"].username, "t1")          # skill + experience outweigh load

    def test_15_strategy_switch_via_settings_api(self):
        self.assertEqual(self.as_(self.admin).patch("/api/settings/", {"assignment_strategy": "LOAD"}, format="json").status_code, 200)
        self.raw_incident(assignee=self.t1, status="IN_PROGRESS")
        r = self.report(self.e1)
        self.assertEqual(r.data["assignee"]["username"], "t2")            # load-based now wins over skills

    def test_16_workload_exceeded(self):
        for t in (self.t1, self.t2):
            t.max_load = 1
            t.save()
            self.raw_incident(assignee=t, status="IN_PROGRESS")
        with self.assertRaises(WorkloadExceeded):
            eligible_technicians()
        r = self.report(self.e1)                                          # still created, awaiting manual assignment
        self.assertEqual((r.status_code, r.data["status"]), (201, "CLASSIFIED"))
        self.assertTrue(AuditLog.objects.filter(incident_id=r.data["id"], action="ASSIGNMENT_FAILED").exists())
        m = self.act(self.admin, r.data["id"], "assign", technician=self.t1.id)
        self.assertEqual((m.status_code, m.data["code"]), (409, "workload_exceeded"))

    def test_17_technician_unavailable(self):
        for t in (self.t1, self.t2):
            t.is_available = False
            t.save()
        r = self.report(self.e1)
        self.assertEqual(r.data["status"], "CLASSIFIED")
        m = self.act(self.admin, r.data["id"], "assign", technician=self.t1.id)
        self.assertEqual(m.data["code"], "technician_unavailable")


class ErrorHandlingTests(Base):
    def test_18_service_not_found(self):
        r = self.report(self.e1, service=9999)
        self.assertEqual((r.status_code, r.data["code"]), (404, "service_not_found"))

    def test_19_missing_sla_configuration(self):
        SLAPolicy.objects.all().delete()
        r = self.report(self.e1)
        self.assertEqual((r.status_code, r.data["code"]), (422, "missing_sla_configuration"))

    def test_20_same_user_duplicate_blocked(self):
        self.assertEqual(self.report(self.e1).status_code, 201)
        r = self.report(self.e1)
        self.assertEqual((r.status_code, r.data["code"]), (409, "duplicate_incident"))


class IntelligenceAndSLATests(Base):
    def test_21_duplicate_detection_links_related_incident(self):
        first = self.report(self.e1).data
        second = self.report(self.e2, title="Payment application failing", description="Payment transactions failing for users").data
        self.assertEqual(second["duplicate_of"], first["id"])
        self.assertTrue(AuditLog.objects.filter(incident_id=second["id"], action="DUPLICATE_DETECTED").exists())

    def test_22_category_suggestion_endpoint(self):
        r = self.as_(self.e1).post("/api/incidents/suggest/", {"title": "VPN not working", "description": "cannot connect"}, format="json")
        self.assertEqual(r.data["category"]["name"], "Network")

    def test_23_sla_breach_and_escalation(self):
        iid = self.report(self.e1).data["id"]                              # assigned but never acknowledged
        now = timezone.now()
        Incident.objects.filter(pk=iid).update(created_at=now - timedelta(minutes=65), response_due=now - timedelta(hours=1))
        out = sla.check_all()
        self.assertGreaterEqual(out["breaches"], 1)
        self.assertGreaterEqual(out["escalations"], 1)
        inc = Incident.objects.get(pk=iid)
        self.assertTrue(inc.response_breached)
        self.assertEqual(inc.escalation_level, 3)
        self.assertEqual(sla.sla_status(inc), "BREACHED")
        self.assertTrue(Notification.objects.filter(recipient=self.admin, incident=inc, channel="SMS").exists())
        self.assertEqual(sla.check_all()["breaches"], 0)                   # idempotent: no duplicate violations

    def test_24_sla_warning_before_deadline(self):
        iid = self.report(self.e1).data["id"]
        self.act(self.t1, iid, "acknowledge")
        now = timezone.now()
        Incident.objects.filter(pk=iid).update(created_at=now - timedelta(minutes=26), resolution_due=now + timedelta(minutes=4))
        self.assertEqual(sla.risk(Incident.objects.get(pk=iid)), "HIGH")
        self.assertEqual(sla.check_all()["warnings"], 1)

    def test_25_notifications_and_search_filters(self):
        self.report(self.e1)
        self.report(self.e1, title="Printer out of paper", description="tray empty", service=self.prn.id, impact=1, urgency=1, affected_users=1)
        self.assertTrue(Notification.objects.filter(recipient=self.t1, channel="IN_APP").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.t1, channel="EMAIL").exists())
        c = self.as_(self.admin)
        self.assertEqual(len(c.get("/api/incidents/?priority=P1").data), 1)
        self.assertEqual(len(c.get("/api/incidents/?q=printer").data), 1)
        self.assertEqual(len(c.get(f"/api/incidents/?service={self.prn.id}").data), 1)
        self.assertEqual(len(c.get("/api/incidents/?status=ASSIGNED").data), 2)
        self.assertEqual(len(c.get("/api/incidents/?sla_status=ON_TRACK").data), 2)

    def test_26_feedback_and_suggested_resolution(self):
        iid = self.report(self.e1).data["id"]
        self.assertEqual(self.as_(self.e1).post(f"/api/incidents/{iid}/feedback/", {"rating": 5}, format="json").status_code, 409)
        self.act(self.t1, iid, "acknowledge")
        self.act(self.t1, iid, "start")
        self.act(self.t1, iid, "resolve", message="Restarted payment gateway")
        self.assertEqual(self.as_(self.e1).post(f"/api/incidents/{iid}/feedback/", {"rating": 5}, format="json").status_code, 200)
        self.assertEqual(self.as_(self.e1).post(f"/api/incidents/{iid}/feedback/", {"rating": 9}, format="json").status_code, 400)
        new = self.report(self.e2, title="Payment application failing", description="Payment transactions failing").data["id"]
        s = self.as_(self.admin).get(f"/api/incidents/{new}/suggestions/")
        self.assertEqual(s.data[0]["resolution"], "Restarted payment gateway")


class InnovationTests(Base):
    def setUp(self):
        super().setUp()
        self.db = Service.objects.create(name="DB", business_criticality=1)
        ServiceDependency.objects.create(service=self.pay, depends_on=self.db)      # Payment depends on DB

    def test_27_dependency_aware_priority(self):
        self.assertEqual(insights.effective_criticality(self.db), 5)                 # inherits Payment's criticality
        r = self.report(self.e1, title="Database slow", description="queries are slow", service=self.db.id, impact=2, urgency=2, affected_users=1)
        self.assertEqual((r.data["score"], r.data["priority"]), (20, "P3"))          # 2x2x5, not 2x2x1 (P4)

    def test_28_circular_dependency_rejected(self):
        r = self.as_(self.admin).post("/api/dependencies/", {"service": self.db.id, "depends_on": self.pay.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.as_(self.e1).post("/api/dependencies/", {"service": self.db.id, "depends_on": self.prn.id}, format="json").status_code, 403)

    def test_29_root_cause_identified_from_upstream_incident(self):
        self.report(self.e2, title="Database down", description="DB server not responding", service=self.db.id)
        pid = self.report(self.e1).data["id"]
        self.assertTrue(AuditLog.objects.filter(incident_id=pid, action="ROOT_CAUSE_IDENTIFIED").exists())
        data = self.as_(self.admin).get(f"/api/incidents/{pid}/insights/").data
        self.assertEqual(data["root_cause"]["service"], "DB")
        self.assertEqual(self.as_(self.e1).get(f"/api/incidents/{pid}/insights/").status_code, 403)
        graph = self.as_(self.e1).get("/api/service-graph/").data
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual({n["name"]: n["health"] for n in graph["nodes"]}["DB"], "critical")

    def test_30_predictive_sla_probability_grows_with_elapsed_time(self):
        iid = self.report(self.e1).data["id"]
        p1 = insights.predict(Incident.objects.get(pk=iid))["probability"]
        now = timezone.now()
        Incident.objects.filter(pk=iid).update(created_at=now - timedelta(minutes=29), resolution_due=now + timedelta(minutes=1))
        p2 = insights.predict(Incident.objects.get(pk=iid))
        self.assertTrue(0 <= p1 < p2 <= 1)
        self.assertIn(p2["level"], ("MEDIUM", "HIGH"))
        self.assertIsNone(insights.predict(self.raw_incident(status="CLOSED", resolution_due=now)))
