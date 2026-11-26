from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.plugins.otp_totp.models import TOTPDevice

from audit.models import EntreeAudit
from comptes.oidc import EntraIdBackend
from comptes.roles import Role, roles_de

from .outils import ajouter_totp, code_valide, creer_interne, creer_prestataire

MDP = "Mot-de-passe-solide-42"


class MfaPrestataireTests(TestCase):
    def setUp(self):
        self.u, _ = creer_prestataire()

    def connecter(self):
        return self.client.post(reverse("comptes:connexion"), {"username": self.u.email, "password": MDP})

    def test_sans_second_facteur_tout_redirige_vers_mfa(self):
        self.connecter()
        for url in (reverse("accueil"), reverse("charte:signer")):
            r = self.client.get(url)
            self.assertRedirects(r, reverse("comptes:mfa"), fetch_redirect_response=False)

    def test_enrolement_totp(self):
        self.connecter()
        r = self.client.get(reverse("comptes:mfa"))
        self.assertTrue(r.context["enrolement"])
        appareil = TOTPDevice.objects.get(user=self.u)
        self.assertFalse(appareil.confirmed)
        r = self.client.post(reverse("comptes:mfa"), {"code": code_valide(appareil)})
        self.assertRedirects(r, reverse("accueil"), fetch_redirect_response=False)
        appareil.refresh_from_db()
        self.assertTrue(appareil.confirmed)
        self.assertEqual(self.client.get(reverse("accueil")).status_code, 200)

    def test_code_invalide_refuse_et_journalise(self):
        ajouter_totp(self.u)
        self.connecter()
        r = self.client.post(reverse("comptes:mfa"), {"code": "000000"})
        self.assertContains(r, "Code invalide")
        self.assertTrue(EntreeAudit.objects.filter(action="Code MFA invalide").exists())

    def test_echec_de_connexion_journalise(self):
        self.client.post(reverse("comptes:connexion"), {"username": self.u.email, "password": "mauvais"})
        self.assertTrue(EntreeAudit.objects.filter(action="Échec de connexion").exists())


class InvitationTests(TestCase):
    def test_invitation_definit_le_mot_de_passe_puis_mfa(self):
        u, _ = creer_prestataire()
        u.set_unusable_password()
        u.save()
        url = reverse("comptes:invitation", args=[urlsafe_base64_encode(force_bytes(u.pk)), default_token_generator.make_token(u)])
        r = self.client.post(url, {"new_password1": "Un-nouveau-mdp-tres-long", "new_password2": "Un-nouveau-mdp-tres-long"})
        self.assertRedirects(r, reverse("comptes:mfa"), fetch_redirect_response=False)
        u.refresh_from_db()
        self.assertTrue(u.check_password("Un-nouveau-mdp-tres-long"))
        # Le lien ne fonctionne qu'une fois.
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_jeton_invalide(self):
        u, _ = creer_prestataire()
        url = reverse("comptes:invitation", args=[urlsafe_base64_encode(force_bytes(u.pk)), "faux-jeton"])
        self.assertEqual(self.client.get(url).status_code, 400)


@override_settings(OIDC_GROUPES_ROLES={"g-rssi": "RSSI", "g-tech": "Référent technique", "g-inconnu": "Pirate"})
class SynchronisationRolesTests(TestCase):
    def test_roles_issus_des_groupes(self):
        u = creer_interne(roles=[Role.DSI])
        EntraIdBackend.synchroniser_roles(u, {"groups": ["g-rssi", "g-tech", "g-inconnu", "g-autre"]})
        u = type(u).objects.get(pk=u.pk)
        self.assertEqual(roles_de(u), {"RSSI", "Référent technique"})

    def test_prestataire_refuse_en_sso(self):
        u, _ = creer_prestataire()
        backend = EntraIdBackend()
        self.assertIsNone(backend.update_user(u, {"email": u.email, "oid": "x"}))
        self.assertFalse(backend.filter_users_by_claims({"email": u.email}).exists())


class EntetesSecuriteTests(TestCase):
    def test_csp_et_entetes(self):
        r = self.client.get(reverse("comptes:connexion"))
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
