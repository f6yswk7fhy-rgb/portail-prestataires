from django.db import connection
from django.test import TestCase

from audit.journal import journaliser
from audit.models import EMPREINTE_INITIALE, EntreeAudit, verifier_chaine


class JournalAuditTests(TestCase):
    def test_entrees_chainees(self):
        a = journaliser("Première action")
        b = journaliser("Deuxième action", details={"x": 1})
        self.assertEqual(a.empreinte_precedente, EMPREINTE_INITIALE)
        self.assertEqual(b.empreinte_precedente, a.empreinte)
        self.assertEqual(verifier_chaine(), [])

    def test_modification_interdite(self):
        e = journaliser("Action")
        e.action = "Falsifiée"
        with self.assertRaises(PermissionError):
            e.save()
        with self.assertRaises(PermissionError):
            e.delete()
        with self.assertRaises(PermissionError):
            EntreeAudit.objects.all().delete()
        with self.assertRaises(PermissionError):
            EntreeAudit.objects.update(action="x")

    def test_falsification_detectee(self):
        journaliser("Action 1")
        e = journaliser("Action 2")
        journaliser("Action 3")
        if connection.vendor == "postgresql":
            self.skipTest("Le trigger PostgreSQL empêche déjà la falsification directe.")
        with connection.cursor() as c:
            c.execute("UPDATE audit_entreeaudit SET action = 'Falsifiée' WHERE id = %s", [e.id])
        self.assertEqual(verifier_chaine(), [e.id])
