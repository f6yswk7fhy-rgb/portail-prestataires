"""Données de démonstration pour un poste de développement. Refuse de s'exécuter hors mode debug."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from charte.models import CharteVersion
from comptes.models import Utilisateur
from prestataires.models import Intervenant, Societe

TEXTE = """Article 1 · Objet
La présente charte fixe les règles d'utilisation du système d'information de l'établissement par les intervenants extérieurs.

Article 2 · Accès nominatifs
Les identifiants sont personnels. Le partage de compte, de code MFA ou de session est interdit.

Article 3 · Accès à la demande
Le compte est désactivé en dehors des interventions validées. Toute ouverture fait l'objet d'une demande motivée.

Article 4 · Confidentialité
L'intervenant n'accède qu'aux données strictement nécessaires à sa mission et respecte le secret professionnel.

Article 5 · Traçabilité
Toutes les connexions et actions sont journalisées et peuvent faire l'objet d'un contrôle.

Article 6 · Incidents
Tout incident de sécurité est signalé sans délai au RSSI.

Article 7 · Fin de mission
L'habilitation prend fin à sa date d'échéance. Aucune donnée n'est conservée par l'intervenant."""


class Command(BaseCommand):
    help = "Crée une société, un intervenant et une charte de démonstration (développement uniquement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Commande réservée au développement (PORTAIL_DEBUG=1).")
        societe, _ = Societe.objects.get_or_create(raison_sociale="MédiSoft (démo)")
        u, cree = Utilisateur.objects.get_or_create(
            email="thomas.girard@demo.invalid", defaults={"first_name": "Thomas", "last_name": "Girard"}
        )
        if cree:
            u.set_password("Demo-prestataire-2026")
            u.save()
        Intervenant.objects.get_or_create(utilisateur=u, defaults={"societe": societe})
        version, _ = CharteVersion.objects.get_or_create(numero="1.0", defaults={"contenu": TEXTE})
        version.publier(None)
        self.stdout.write(
            self.style.SUCCESS(
                "Démo prête : connexion thomas.girard@demo.invalid / Demo-prestataire-2026 "
                "(une application TOTP sera demandée)."
            )
        )
