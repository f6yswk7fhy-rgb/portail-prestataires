"""Journal d'audit en ajout seul, chaîné par empreintes SHA-256.

Chaque entrée contient l'empreinte de l'entrée précédente : modifier ou
supprimer une ligne casse la chaîne, ce que détecte `verifier_chaine()`
(commande `python manage.py verifier_audit`). Sous PostgreSQL, un trigger
interdit en plus toute mise à jour ou suppression (voir la migration 0002).
"""

import hashlib
import json

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

EMPREINTE_INITIALE = "0" * 64


class EntreeAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Le journal d'audit est en ajout seul.")

    def delete(self):
        raise PermissionError("Le journal d'audit est en ajout seul.")


class EntreeAudit(models.Model):
    horodatage = models.DateTimeField(default=timezone.now, editable=False)
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    acteur_libelle = models.CharField(max_length=200, help_text="Nom de l'acteur au moment de l'action, ou « Système ».")
    action = models.CharField(max_length=100)
    objet_type = models.CharField(max_length=100, blank=True)
    objet_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    empreinte_precedente = models.CharField(max_length=64, editable=False)
    empreinte = models.CharField(max_length=64, unique=True, editable=False)

    objects = EntreeAuditQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        verbose_name = "entrée d'audit"
        verbose_name_plural = "journal d'audit"

    def __str__(self):
        return f"{self.horodatage:%Y-%m-%d %H:%M:%S} · {self.acteur_libelle} · {self.action}"

    def contenu_canonique(self):
        return json.dumps(
            {
                "horodatage": self.horodatage.isoformat(),
                "acteur": self.acteur_id,
                "acteur_libelle": self.acteur_libelle,
                "action": self.action,
                "objet_type": self.objet_type,
                "objet_id": self.objet_id,
                "details": self.details,
                "adresse_ip": self.adresse_ip,
                "empreinte_precedente": self.empreinte_precedente,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def calculer_empreinte(self):
        return hashlib.sha256(self.contenu_canonique().encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("Le journal d'audit est en ajout seul.")
        with transaction.atomic():
            derniere = EntreeAudit.objects.select_for_update().order_by("-id").first()
            self.empreinte_precedente = derniere.empreinte if derniere else EMPREINTE_INITIALE
            self.empreinte = self.calculer_empreinte()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Le journal d'audit est en ajout seul.")


def verifier_chaine():
    """Renvoie la liste des identifiants d'entrées dont l'empreinte ou le chaînage est incorrect."""
    anomalies = []
    precedente = EMPREINTE_INITIALE
    for entree in EntreeAudit.objects.order_by("id").iterator():
        if entree.empreinte_precedente != precedente or entree.calculer_empreinte() != entree.empreinte:
            anomalies.append(entree.id)
        precedente = entree.empreinte
    return anomalies
