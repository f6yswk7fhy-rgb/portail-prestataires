from django.core.management.base import BaseCommand, CommandError

from audit.models import EntreeAudit, verifier_chaine


class Command(BaseCommand):
    help = "Vérifie l'intégrité du chaînage du journal d'audit."

    def handle(self, *args, **options):
        anomalies = verifier_chaine()
        if anomalies:
            raise CommandError(f"Chaîne d'audit rompue sur les entrées : {anomalies}")
        self.stdout.write(self.style.SUCCESS(f"Journal intègre ({EntreeAudit.objects.count()} entrées)."))
