from datetime import timedelta

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from acces import workflow as wf
from acces.models import Application, Habilitation, Intervention, TacheTechnique
from audit.models import EntreeAudit, verifier_chaine
from charte.models import CharteVersion, Signature
from comptes.models import Utilisateur

from .outils import ajouter_totp, creer_interne, creer_prestataire

H, I, T = Habilitation.Statut, Intervention.Statut, TacheTechnique.Type


class Base(TestCase):
    def setUp(self):
        self.rssi = creer_interne("rssi@ch.fr", roles=["RSSI"])
        self.dsi = creer_interne("dsi@ch.fr", roles=["DSI"])
        self.ref_int = creer_interne("chef@ch.fr", roles=["Référent interne"])
        self.ref_app = creer_interne("pacs@ch.fr")
        self.tech = creer_interne("tech@ch.fr", roles=["Référent technique"])
        self.autre = creer_interne("autre@ch.fr")
        self.app = Application.objects.create(nom="PACS imagerie")
        self.app.referents_applicatifs.add(self.ref_app)
        self.charte = CharteVersion.objects.create(numero="1.0", contenu="Texte")
        self.charte.publier(self.rssi)
        self.presta, self.intervenant = creer_prestataire()

    def req(self, user):
        r = RequestFactory().post("/")
        r.user = user
        return r

    def signer(self):
        Signature.objects.create(intervenant=self.intervenant, version=self.charte)

    def habilitation(self, signee=True):
        if signee:
            self.signer()
        return wf.creer_habilitation(
            self.req(self.ref_int),
            intervenant=self.intervenant,
            application=self.app,
            justification="Maintenance du PACS",
            date_fin=timezone.localdate() + timedelta(days=90),
        )

    def dormante(self):
        h = self.habilitation()
        wf.decider_habilitation(self.req(self.rssi), h, True)
        wf.confirmer_tache(self.req(self.tech), h.taches.get(type=T.CREATION_BEYONDTRUST))
        h.refresh_from_db()
        return h

    def creneau(self, heures=4):
        debut = timezone.now() + timedelta(hours=1)
        return debut, debut + timedelta(hours=heures)


class HabilitationTests(Base):
    def test_attend_la_charte_puis_passe_en_validation(self):
        h = self.habilitation(signee=False)
        self.assertEqual(h.statut, H.ATTENTE_CHARTE)
        self.signer()
        wf.apres_signature(self.req(self.presta), self.intervenant)
        h.refresh_from_db()
        self.assertEqual(h.statut, H.EN_VALIDATION)

    def test_seul_le_rssi_valide(self):
        h = self.habilitation()
        for u in (self.ref_int, self.dsi, self.ref_app, self.presta):
            with self.assertRaises(PermissionDenied):
                wf.decider_habilitation(self.req(u), h, True)

    def test_validation_cree_la_tache_beyondtrust_puis_dormante(self):
        h = self.habilitation()
        wf.decider_habilitation(self.req(self.rssi), h, True)
        self.assertEqual(h.statut, H.PREPARATION)
        tache = h.taches.get()
        self.assertEqual(tache.type, T.CREATION_BEYONDTRUST)
        wf.confirmer_tache(self.req(self.tech), tache)
        h.refresh_from_db()
        self.assertEqual(h.statut, H.DORMANTE)

    def test_sans_beyondtrust_directement_dormante(self):
        self.app.creation_beyondtrust = False
        self.app.save()
        h = self.habilitation()
        wf.decider_habilitation(self.req(self.rssi), h, True)
        self.assertEqual(h.statut, H.DORMANTE)

    def test_refus_exige_un_motif(self):
        h = self.habilitation()
        with self.assertRaises(ValidationError):
            wf.decider_habilitation(self.req(self.rssi), h, False, "")
        wf.decider_habilitation(self.req(self.rssi), h, False, "Besoin non justifié")
        self.assertEqual(h.statut, H.REFUSEE)

    def test_duree_maximale_un_an(self):
        self.signer()
        with self.assertRaises(ValidationError):
            wf.creer_habilitation(
                self.req(self.ref_int), intervenant=self.intervenant, application=self.app,
                justification="x", date_fin=timezone.localdate() + timedelta(days=400),
            )

    def test_creation_reservee_aux_referents(self):
        self.signer()
        with self.assertRaises(PermissionDenied):
            wf.creer_habilitation(
                self.req(self.autre), intervenant=self.intervenant, application=self.app,
                justification="x", date_fin=timezone.localdate() + timedelta(days=30),
            )


class InterventionTests(Base):
    def test_parcours_complet_demande_par_le_prestataire(self):
        h = self.dormante()
        i = wf.demander_intervention(self.req(self.presta), h, "Ticket 4587", *self.creneau())
        self.assertEqual(i.statut, I.DEMANDEE)
        with self.assertRaises(PermissionDenied):
            wf.decider_intervention(self.req(self.autre), i, True)
        wf.decider_intervention(self.req(self.ref_app), i, True)
        self.assertEqual(i.statut, I.A_OUVRIR)
        wf.confirmer_tache(self.req(self.tech), i.taches.get(type=T.OUVERTURE))
        i.refresh_from_db()
        self.assertEqual(i.statut, I.OUVERTE)
        fermeture = i.taches.get(type=T.FERMETURE)
        self.assertEqual(fermeture.a_faire_avant, i.fin)
        wf.confirmer_tache(self.req(self.tech), fermeture)
        i.refresh_from_db()
        self.assertEqual(i.statut, I.FERMEE)
        self.assertEqual(verifier_chaine(), [])

    def test_validation_d_office_par_referent_applicatif_ou_dsi(self):
        h = self.dormante()
        i = wf.demander_intervention(self.req(self.ref_app), h, "Urgence", *self.creneau())
        self.assertEqual(i.statut, I.A_OUVRIR)
        i.statut = I.FERMEE
        i.save()
        i2 = wf.demander_intervention(self.req(self.dsi), h, "Astreinte", *self.creneau())
        self.assertEqual(i2.statut, I.A_OUVRIR)

    def test_tiers_ne_peut_pas_demander(self):
        h = self.dormante()
        with self.assertRaises(PermissionDenied):
            wf.demander_intervention(self.req(self.autre), h, "x", *self.creneau())

    def test_creneau_limite_a_8_heures(self):
        h = self.dormante()
        with self.assertRaises(ValidationError):
            wf.demander_intervention(self.req(self.presta), h, "Long", *self.creneau(heures=9))

    def test_une_seule_intervention_a_la_fois(self):
        h = self.dormante()
        wf.demander_intervention(self.req(self.presta), h, "A", *self.creneau())
        with self.assertRaises(ValidationError):
            wf.demander_intervention(self.req(self.presta), h, "B", *self.creneau())

    def test_charte_non_signee_bloque_les_interventions(self):
        h = self.dormante()
        v2 = CharteVersion.objects.create(numero="2.0", contenu="Nouveau texte")
        v2.publier(self.rssi)
        with self.assertRaises(ValidationError):
            wf.demander_intervention(self.req(self.presta), h, "x", *self.creneau())

    def test_habilitation_non_dormante_bloque(self):
        h = self.habilitation()
        with self.assertRaises(ValidationError):
            wf.demander_intervention(self.req(self.presta), h, "x", *self.creneau())

    def test_seul_le_referent_technique_confirme(self):
        h = self.habilitation()
        wf.decider_habilitation(self.req(self.rssi), h, True)
        with self.assertRaises(PermissionDenied):
            wf.confirmer_tache(self.req(self.rssi), h.taches.get())

    def test_revocation_ferme_en_urgence(self):
        h = self.dormante()
        i = wf.demander_intervention(self.req(self.ref_app), h, "x", *self.creneau())
        wf.confirmer_tache(self.req(self.tech), i.taches.get(type=T.OUVERTURE))
        wf.revoquer(self.req(self.dsi), h, "Départ du prestataire")
        h.refresh_from_db()
        self.assertEqual(h.statut, H.REVOQUEE)
        fermeture = i.taches.get(type=T.FERMETURE)
        self.assertLessEqual(fermeture.a_faire_avant, timezone.now())
        self.assertIn(fermeture, wf.taches_en_attente())

    def test_revocation_annule_les_demandes(self):
        h = self.dormante()
        i = wf.demander_intervention(self.req(self.ref_app), h, "x", *self.creneau())
        wf.revoquer(self.req(self.rssi), h, "Fin de contrat")
        i.refresh_from_db()
        self.assertEqual(i.statut, I.ANNULEE)
        self.assertNotIn(i.taches.get(type=T.OUVERTURE), wf.taches_en_attente())


class EcransTests(Base):
    def test_creation_avec_invitation(self):
        self.client.force_login(self.ref_int)
        r = self.client.post(reverse("acces:nouvelle"), {
            "email": "Nina.Roux@Presta.fr", "prenom": "Nina", "nom": "Roux", "nouvelle_societe": "Infogérance Ouest",
            "application": self.app.pk, "risque": "moyen",
            "date_fin": (timezone.localdate() + timedelta(days=60)).isoformat(), "justification": "Sauvegardes",
        })
        h = Habilitation.objects.get()
        self.assertRedirects(r, reverse("acces:detail", args=[h.pk]))
        self.assertEqual(h.intervenant.utilisateur.email, "nina.roux@presta.fr")
        self.assertFalse(h.intervenant.utilisateur.has_usable_password())
        self.assertEqual(h.statut, H.ATTENTE_CHARTE)
        self.assertEqual(len(mail.outbox), 1)

    def test_compte_interne_refuse_comme_intervenant(self):
        self.client.force_login(self.ref_int)
        r = self.client.post(reverse("acces:nouvelle"), {
            "email": self.rssi.email, "prenom": "X", "nom": "Y", "nouvelle_societe": "Z", "application": self.app.pk,
            "risque": "moyen", "date_fin": (timezone.localdate() + timedelta(days=60)).isoformat(), "justification": "x",
        })
        self.assertContains(r, "pas un intervenant")
        self.assertFalse(Habilitation.objects.exists())

    def test_visibilite(self):
        h = self.dormante()
        self.client.force_login(self.autre)
        self.assertEqual(self.client.get(reverse("acces:detail", args=[h.pk])).status_code, 404)
        self.client.force_login(self.ref_app)
        self.assertEqual(self.client.get(reverse("acces:detail", args=[h.pk])).status_code, 200)
        autre_presta, _ = creer_prestataire("autre@presta.fr")
        ajouter_totp(autre_presta)
        self.client.force_login(autre_presta)
        session = self.client.session
        session["otp_device_id"] = autre_presta.totpdevice_set.get().persistent_id
        session.save()
        self.assertEqual(self.client.get(reverse("acces:detail", args=[h.pk])).status_code, 404)

    def test_parcours_par_les_ecrans(self):
        h = self.dormante()
        debut, fin = self.creneau()
        self.client.force_login(self.ref_app)
        self.client.post(reverse("acces:demander_intervention", args=[h.pk]), {
            "motif": "Ticket 12", "debut": timezone.localtime(debut).strftime("%Y-%m-%dT%H:%M"),
            "fin": timezone.localtime(fin).strftime("%Y-%m-%dT%H:%M"),
        })
        i = Intervention.objects.get()
        self.assertEqual(i.statut, I.A_OUVRIR)
        self.client.force_login(self.tech)
        r = self.client.get(reverse("acces:taches"))
        self.assertContains(r, "Activer le compte AD")
        self.client.post(reverse("acces:confirmer_tache", args=[i.taches.get().pk]))
        i.refresh_from_db()
        self.assertEqual(i.statut, I.OUVERTE)
        self.assertTrue(EntreeAudit.objects.filter(action="Tâche confirmée : Activer le compte AD").exists())

    def test_taches_reservees_au_referent_technique(self):
        self.client.force_login(self.rssi)
        self.assertEqual(self.client.get(reverse("acces:taches")).status_code, 403)

    def test_redirection_apres_decision_sans_url_externe(self):
        h = self.dormante()
        i = wf.demander_intervention(self.req(self.presta), h, "x", *self.creneau())
        self.client.force_login(self.ref_app)
        r = self.client.post(reverse("acces:decider_intervention", args=[i.pk]), {"decision": "valider", "retour": "https://evil.example"})
        self.assertRedirects(r, reverse("acces:liste"))

    def test_utilisateur_type(self):
        self.assertTrue(Utilisateur.objects.get(pk=self.presta.pk).est_prestataire)
