import time

from django.core.management.base import BaseCommand

from itsm.sla import SlaMonitor


class Command(BaseCommand):
    help = "Check SLA warnings, violations and escalations once, or continuously with --loop."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, **options):
        while True:
            report = SlaMonitor().run()
            self.stdout.write(f"warnings={report.warnings} violations={report.violations} "
                              f"escalations={report.escalations}")
            if not options["loop"]:
                return
            time.sleep(options["interval"])
