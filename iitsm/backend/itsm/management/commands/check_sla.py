import time

from django.core.management.base import BaseCommand

from itsm.sla import check_all


class Command(BaseCommand):
    help = "Run the SLA monitor (warnings, violations, escalation). Use --loop for continuous background monitoring."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *a, **o):
        while True:
            self.stdout.write(str(check_all()))
            if not o["loop"]:
                break
            time.sleep(o["interval"])
