from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from itsm import services
from itsm.assignment import (LoadBasedAssignmentStrategy, RoundRobinAssignmentStrategy,
                             SkillBasedAssignmentStrategy, pick_technician)
from itsm.exceptions import (DependencyCycle, DuplicateIncident, InvalidStateTransition, InvalidUserInput,
                             MissingSlaConfiguration, TechnicianUnavailable, TechnicianWorkloadExceeded,
                             UnauthorizedOperation)
from itsm.factories import UserFactory
from itsm.insights import add_dependency, find_probable_root_cause
from itsm.intelligence import correlate_open_incidents, suggest_category, suggest_resolutions
from itsm.lifecycle import transition
from itsm.models import (AuditEvent, Category, Incident, IncidentStatus as S, Notification, Service, SlaPolicy,
                         SystemConfiguration, User)
from itsm.priority import RuleBasedPriorityStrategy, WeightedScoringPriorityStrategy
from itsm.sla import SlaMonitor, SlaStatus, apply_sla_deadlines, check_sla_compliance, find_sla_policy


class WorldTestCase(TestCase):
    """A small organisation: three services, two skilled technicians, two employees, two administrators."""

    @classmethod
    def setUpTestData(cls):
        SystemConfiguration.current()
        cls.database_category = Category.objects.create(name="Database", keywords="database sql query replication")
        cls.application_category = Category.objects.create(name="Application", keywords="application portal payment checkout")
        cls.other_category = Category.objects.create(name="Other")
        cls.payment = Service.objects.create(name="Payment Application", keywords="payment transaction checkout card",
                                             business_criticality=5, default_category=cls.application_category)
        cls.database = Service.objects.create(name="Core Database", keywords="database sql query",
                                              business_criticality=2, default_category=cls.database_category)
        cls.general = Service.objects.create(name="General IT", business_criticality=1,
                                             default_category=cls.other_category)
        for priority, response, resolution in (("P1", 5, 30), ("P2", 15, 120), ("P3", 60, 480), ("P4", 240, 1440)):
            SlaPolicy.objects.create(priority=priority, response_minutes=response, resolution_minutes=resolution)
        cls.admin = User.objects.create_user("admin", password="x", role=User.Role.ADMINISTRATOR)
        cls.manager = User.objects.create_user("manager", password="x", role=User.Role.ADMINISTRATOR, is_it_manager=True)
        cls.database_technician = User.objects.create_user("t101", password="x", role=User.Role.TECHNICIAN,
                                                           experience_years=8, max_active_incidents=2)
        cls.database_technician.skills.set([cls.database_category])
        cls.application_technician = User.objects.create_user("t102", password="x", role=User.Role.TECHNICIAN,
                                                              experience_years=4, max_active_incidents=2)
        cls.application_technician.skills.set([cls.application_category])
        cls.employee = User.objects.create_user("e101", password="x", role=User.Role.EMPLOYEE)
        cls.other_employee = User.objects.create_user("e102", password="x", role=User.Role.EMPLOYEE)

    def report(self, reporter=None, title="Payment application unavailable",
               description="Users are unable to complete transactions at checkout", impact=4, urgency=4,
               affected_users=150, service=None):
        service = service or self.payment
        return services.create_incident(reporter or self.employee, title, description, impact, urgency,
                                        affected_users, service.pk)


class PriorityTests(WorldTestCase):
    def test_score_bands_follow_the_documented_thresholds(self):
        weighted = WeightedScoringPriorityStrategy()
        self.assertEqual(weighted.calculate(4, 4, 3, 1).priority, "P1")   # 48
        self.assertEqual(weighted.calculate(4, 4, 2, 1).priority, "P2")   # 32
        self.assertEqual(weighted.calculate(2, 2, 2, 1).priority, "P3")   # 8
        self.assertEqual(weighted.calculate(1, 1, 1, 1).priority, "P4")   # 1

    def test_many_affected_users_raise_the_score(self):
        weighted = WeightedScoringPriorityStrategy()
        self.assertEqual(weighted.calculate(2, 4, 3, 1).score, 24)
        self.assertEqual(weighted.calculate(2, 4, 3, 100).score, 36)

    def test_rule_based_strategy_forces_p1_on_critical_services(self):
        weighted, rule = WeightedScoringPriorityStrategy(), RuleBasedPriorityStrategy()
        self.assertNotEqual(weighted.calculate(3, 1, 5, 1).priority, "P1")
        self.assertEqual(rule.calculate(3, 1, 5, 1).priority, "P1")

    def test_service_inherits_criticality_from_services_that_rely_on_it(self):
        add_dependency(self.payment, self.database)  # payment relies on the database
        incident = self.report(service=self.database, impact=4, urgency=4, affected_users=1)
        self.assertEqual(incident.priority_score, 80)  # criticality raised from 2 to 5
        self.assertTrue(any("relies on" in line for line in incident.priority_rationale))


class LifecycleTests(WorldTestCase):
    def test_new_incident_cannot_jump_straight_to_closed(self):
        incident = Incident(reporter=self.employee, title="x" * 6, description="y" * 12, impact=1, urgency=1)
        with self.assertRaises(InvalidStateTransition):
            transition(incident, S.CLOSED)

    def test_assigned_state_requires_a_technician(self):
        incident = Incident(reporter=self.employee, title="x" * 6, description="y" * 12, impact=1, urgency=1,
                            status=S.CLASSIFIED)
        with self.assertRaises(InvalidStateTransition):
            transition(incident, S.ASSIGNED)

    def test_full_lifecycle_records_every_timestamp(self):
        incident = self.report()
        technician = incident.assignee
        for action, payload in (("acknowledge", {}), ("start", {}), ("resolve", {"resolution": "Restarted gateway"}),
                                ("verify", {}), ("close", {})):
            actor = self.employee if action == "verify" else technician
            incident = services.perform_action(incident, action, actor, payload)
        incident.refresh_from_db()
        self.assertEqual(incident.status, S.CLOSED)
        for stamp in (incident.acknowledged_at, incident.resolved_at, incident.verified_at, incident.closed_at):
            self.assertIsNotNone(stamp)

    def test_resolving_without_a_resolution_is_rejected(self):
        incident = self.report()
        services.perform_action(incident, "acknowledge", incident.assignee)
        services.perform_action(incident, "start", incident.assignee)
        with self.assertRaises(InvalidUserInput):
            services.perform_action(incident, "resolve", incident.assignee, {"resolution": "  "})

    def test_reopening_a_resolved_incident_counts_the_reopen(self):
        incident = self.report()
        t = incident.assignee
        for action, payload in (("acknowledge", {}), ("start", {}), ("resolve", {"resolution": "Fixed"})):
            services.perform_action(incident, action, t, payload)
        services.perform_action(incident, "reopen", self.employee, {"reason": "Still failing"})
        incident.refresh_from_db()
        self.assertEqual((incident.status, incident.reopen_count), (S.IN_PROGRESS, 1))

    def test_only_legal_actions_are_offered_for_the_current_status(self):
        incident = self.report()
        technician_keys = {a["key"] for a in services.available_actions(incident, incident.assignee)}
        self.assertEqual(technician_keys, {"acknowledge"})
        self.assertNotIn("close", technician_keys)


class AssignmentTests(WorldTestCase):
    def test_new_incident_is_assigned_automatically_to_the_skilled_technician(self):
        incident = self.report()
        self.assertEqual((incident.status, incident.assignee), (S.ASSIGNED, self.application_technician))

    def test_skill_based_strategy_prefers_matching_skills(self):
        incident = self.report()
        ranking = SkillBasedAssignmentStrategy().rank(
            incident, [self.database_technician, self.application_technician], {})
        self.assertEqual(ranking[0].technician, self.application_technician)

    def test_load_based_strategy_prefers_the_least_loaded_technician(self):
        incident = self.report()
        loads = {self.application_technician.pk: 2, self.database_technician.pk: 0}
        ranking = LoadBasedAssignmentStrategy().rank(
            incident, [self.application_technician, self.database_technician], loads)
        self.assertEqual(ranking[0].technician, self.database_technician)

    def test_round_robin_takes_turns(self):
        incident = self.report()
        strategy = RoundRobinAssignmentStrategy()
        first = pick_technician(incident, strategy).technician
        second = pick_technician(incident, strategy).technician
        self.assertNotEqual(first, second)

    def test_incident_stays_classified_when_nobody_is_available(self):
        User.objects.filter(role=User.Role.TECHNICIAN).update(is_available=False)
        incident = self.report()
        self.assertEqual(incident.status, S.CLASSIFIED)
        self.assertTrue(AuditEvent.objects.filter(incident=incident, action="AssignmentPending").exists())

    def test_workload_limit_is_enforced_on_manual_assignment(self):
        for reporter, title, description in ((self.employee, "Database reports are slow", "Queries on the reporting server are slow"),
                                             (self.other_employee, "Replica lagging behind", "Replication on the standby is minutes behind")):
            self.report(reporter=reporter, title=title, service=self.database, description=description,
                        impact=1, urgency=1, affected_users=1)
        incident = self.report(title="Another unrelated checkout failure", description="Checkout page blank for me")
        Incident.objects.exclude(pk=incident.pk).update(assignee=self.database_technician,
                                                        status=S.IN_PROGRESS)
        with self.assertRaises(TechnicianWorkloadExceeded):
            services.assign_incident(incident, self.database_technician, self.admin)

    def test_unavailable_technician_cannot_be_assigned(self):
        incident = self.report()
        User.objects.filter(pk=self.database_technician.pk).update(is_available=False)
        self.database_technician.refresh_from_db()
        with self.assertRaises(TechnicianUnavailable):
            services.assign_incident(incident, self.database_technician, self.admin)


class SlaTests(WorldTestCase):
    def test_deadlines_come_from_the_policy_for_the_priority(self):
        incident = self.report()
        self.assertEqual(incident.response_due_at - incident.created_at, timedelta(minutes=5))
        self.assertEqual(incident.resolution_due_at - incident.created_at, timedelta(minutes=30))

    def test_service_specific_policy_overrides_the_default(self):
        SlaPolicy.objects.create(priority="P1", service=self.payment, response_minutes=2, resolution_minutes=10)
        self.assertEqual(find_sla_policy("P1", self.payment).resolution_minutes, 10)
        self.assertEqual(find_sla_policy("P1", self.database).resolution_minutes, 30)

    def test_missing_policy_is_reported_clearly(self):
        SlaPolicy.objects.filter(priority="P4").delete()
        with self.assertRaises(MissingSlaConfiguration):
            self.report(impact=1, urgency=1, affected_users=1, service=self.general,
                        title="Install my design tool", description="Please install the licensed design tool")

    def test_missed_response_deadline_is_recorded_once_and_escalated(self):
        incident = self.report()
        past = timezone.now() - timedelta(minutes=20)
        Incident.objects.filter(pk=incident.pk).update(created_at=past, response_due_at=past + timedelta(minutes=5),
                                                       resolution_due_at=past + timedelta(minutes=30))
        first = SlaMonitor().run()
        second = SlaMonitor().run()
        incident.refresh_from_db()
        self.assertTrue(incident.response_breached)
        self.assertEqual(incident.escalation_level, 4)  # technician -> lead -> admin -> IT manager
        self.assertIn(incident.code, first.violations)
        self.assertEqual(second.violations, [])
        self.assertEqual(check_sla_compliance(incident).status, SlaStatus.BREACHED)

    def test_warning_is_raised_at_eighty_percent_of_the_window(self):
        incident = self.report(impact=2, urgency=2, affected_users=1, service=self.database,
                               title="Database report slow", description="Queries are slow on the server")
        start = timezone.now() - timedelta(minutes=50)  # P3 response window is 60 minutes
        Incident.objects.filter(pk=incident.pk).update(created_at=start, response_due_at=start + timedelta(minutes=60),
                                                       resolution_due_at=start + timedelta(minutes=480))
        self.assertIn(incident.code, SlaMonitor().run().warnings)


class IntelligenceTests(WorldTestCase):
    def test_category_is_suggested_from_the_description(self):
        names = [s["name"] for s in suggest_category("sql query on the database is very slow")]
        self.assertEqual(names[0], "Database")

    def test_similar_report_from_another_employee_is_flagged_as_duplicate(self):
        original = self.report()
        repeat = self.report(reporter=self.other_employee, title="Payment application is not working",
                             description="Users cannot complete payment transactions at checkout")
        self.assertEqual(repeat.duplicate_of, original)

    def test_same_reporter_cannot_file_the_same_open_incident_twice(self):
        self.report()
        with self.assertRaises(DuplicateIncident):
            self.report()

    def test_related_open_incidents_are_clustered(self):
        self.report()
        self.report(reporter=self.other_employee, title="Payment transactions failing",
                    description="Checkout shows an error when paying", impact=3, urgency=3, affected_users=5)
        clusters = correlate_open_incidents()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["size"], 2)

    def test_resolution_from_a_similar_past_incident_is_suggested(self):
        incident = self.report()
        for action, payload in (("acknowledge", {}), ("start", {}),
                                ("resolve", {"resolution": "Restarted the payment gateway service"})):
            services.perform_action(incident, action, incident.assignee, payload)
        suggestions = suggest_resolutions("payment transactions are failing at checkout")
        self.assertEqual(suggestions[0]["resolution"], "Restarted the payment gateway service")

    def test_free_text_search_ranks_by_similarity_and_finds_by_code(self):
        payment = self.report()
        self.report(reporter=self.other_employee, title="Database queries slow", description="Reports time out",
                    service=self.database, impact=1, urgency=1, affected_users=1)
        found = services.search_incidents(self.admin, {"q": "payment checkout"})
        self.assertEqual(found[0].pk, payment.pk)
        self.assertEqual([i.pk for i in services.search_incidents(self.admin, {"q": payment.code})], [payment.pk])

    def test_joining_an_incident_raises_affected_users_and_priority(self):
        incident = self.report(impact=2, urgency=3, affected_users=15, service=self.payment)
        before = incident.priority_score
        services.join_incident(incident, self.other_employee)
        incident.refresh_from_db()
        self.assertEqual(incident.affected_users, 16)
        self.assertGreaterEqual(incident.priority_score, before)


class InsightTests(WorldTestCase):
    def test_dependency_cycles_are_rejected(self):
        add_dependency(self.payment, self.database)
        with self.assertRaises(DependencyCycle):
            add_dependency(self.database, self.payment)

    def test_probable_root_cause_is_found_on_an_upstream_service(self):
        add_dependency(self.payment, self.database)
        cause = self.report(service=self.database, title="Database is down", description="The database server is down")
        effect = self.report(reporter=self.other_employee, title="Payments failing",
                             description="Cannot pay at checkout", service=self.payment)
        self.assertEqual(find_probable_root_cause(effect), cause)
        effect.refresh_from_db()
        self.assertEqual(effect.probable_root_cause, cause)


class AuditAndNotificationTests(WorldTestCase):
    def test_creating_an_incident_writes_audit_events_and_notifies_people(self):
        incident = self.report()
        actions = list(AuditEvent.objects.filter(incident=incident).values_list("action", flat=True))
        for expected in ("IncidentReported", "IncidentClassified", "TechnicianAssigned"):
            self.assertIn(expected, actions)
        self.assertTrue(Notification.objects.filter(recipient=self.application_technician, channel="IN_APP").exists())
        self.assertTrue(Notification.objects.filter(channel="EMAIL").exists())
        self.assertTrue(Notification.objects.filter(channel="SMS").exists())  # P1 assignment


class SecurityTests(WorldTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_login_with_a_wrong_password_is_rejected(self):
        response = self.client.post("/api/auth/login/", {"username": "e101", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_login_returns_a_token_and_role(self):
        self.employee.set_password("pass1234")
        self.employee.save()
        response = self.client.post("/api/auth/login/", {"username": "e101", "password": "pass1234"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "EMPLOYEE")

    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get("/api/incidents/").status_code, 401)

    def test_employee_cannot_open_someone_elses_incident(self):
        incident = self.report(reporter=self.employee)
        self.client.force_authenticate(self.other_employee)
        self.assertEqual(self.client.get(f"/api/incidents/{incident.pk}/").status_code, 404)

    def test_employee_cannot_assign_incidents(self):
        incident = self.report()
        self.client.force_authenticate(self.employee)
        response = self.client.post(f"/api/incidents/{incident.pk}/assign/",
                                    {"technician": self.database_technician.pk}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_acknowledge_for_the_technician(self):
        incident = self.report()
        with self.assertRaises(UnauthorizedOperation):
            services.perform_action(incident, "acknowledge", self.employee)

    def test_employees_never_receive_internal_notes_or_insights(self):
        incident = self.report()
        services.add_comment(incident, incident.assignee, "Checking the gateway logs", internal=True)
        self.client.force_authenticate(self.employee)
        body = self.client.get(f"/api/incidents/{incident.pk}/").data
        self.assertEqual(body["comments"], [])
        self.assertEqual(self.client.get(f"/api/incidents/{incident.pk}/insights/").status_code, 403)

    def test_invalid_incident_input_is_rejected_with_a_clear_message(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post("/api/incidents/", {"title": "Hi", "description": "short", "impact": 9,
                                                       "urgency": 1}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_weak_passwords_are_rejected_at_registration(self):
        with self.assertRaises(InvalidUserInput):
            UserFactory.create("newperson", "123")

    def test_deactivating_a_user_keeps_their_incidents(self):
        incident = self.report()
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/users/{self.employee.pk}/").status_code, 204)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.assertTrue(Incident.objects.filter(pk=incident.pk).exists())

    def test_passwords_are_stored_hashed(self):
        user = UserFactory.create("freshuser", "a-long-Safe-passphrase-42")
        self.assertNotEqual(user.password, "a-long-Safe-passphrase-42")
        self.assertTrue(user.check_password("a-long-Safe-passphrase-42"))
