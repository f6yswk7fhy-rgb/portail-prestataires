from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from audit.models import EntreeAudit, verifier_chaine
from charte.models import CharteVersion, Signature

from .outils import ajouter_totp, code_valide, creer_interne, creer_prestataire


class CharteTests(TestCase):
    def setUp(self):
        self.rssi = creer_interne()
        self.v = CharteVersion.objects.create(numero="3.2", contenu="Article 1.\n\nArticle 2.")
        self.v.publier(self.rssi)
        self.u, self.intervenant = creer_prestataire()
        self.appareil = ajouter_totp(self.u)
        self.client.force_login(self.u)
        session = self.client.session
        session["otp_device_id"] = self.appareil.persistent_id
        session.save()

    def test_version_publiee_immuable(self):
        self.v.contenu = "Texte modifié"
        with self.assertRaises(ValidationError):
            self.v.save()

    def test_une_seule_version_active(self):
        v2 = CharteVersion.objects.create(numero="3.3", contenu="Nouveau texte")
        v2.publier(self.rssi)
        self.assertEqual(CharteVersion.active(), v2)
        self.assertFalse(CharteVersion.objects.get(pk=self.v.pk).en_vigueur)

    def test_signature_complete(self):
        r = self.client.post(reverse("charte:signer"), {"engagement": "on", "code": code_valide(self.appareil)})
        self.assertRedirects(r, reverse("charte:signer"))
        s = Signature.objects.get()
        self.assertTrue(s.mfa_verifiee)
        self.assertEqual(s.empreinte_document, self.v.empreinte)
        self.assertEqual(s.preuve, s.calculer_preuve())
        self.assertTrue(EntreeAudit.objects.filter(action="Charte v3.2 signée").exists())
        self.assertEqual(verifier_chaine(), [])
        self.assertContains(self.client.get(reverse("charte:signer")), "signée")

    def test_signature_refusee_sans_engagement_ou_code(self):
        self.client.post(reverse("charte:signer"), {"code": code_valide(self.appareil)})
        self.client.post(reverse("charte:signer"), {"engagement": "on", "code": "123456"})
        self.assertFalse(Signature.objects.exists())

    def test_nouvelle_version_exige_une_nouvelle_signature(self):
        self.client.post(reverse("charte:signer"), {"engagement": "on", "code": code_valide(self.appareil)})
        v2 = CharteVersion.objects.create(numero="3.3", contenu="Nouveau texte")
        v2.publier(self.rssi)
        self.assertFalse(self.intervenant.a_signe(v2))
        self.assertContains(self.client.get(reverse("accueil")), "Signature de la charte requise")


class AccesJournalTests(TestCase):
    def test_reserve_rssi_dsi(self):
        self.client.force_login(creer_interne("ref@etablissement.fr", roles=["Référent technique"]))
        self.assertEqual(self.client.get(reverse("audit:journal")).status_code, 403)
        self.client.force_login(creer_interne("rssi2@etablissement.fr", roles=["RSSI"]))
        self.assertEqual(self.client.get(reverse("audit:journal")).status_code, 200)
