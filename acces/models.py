"""Habilitations (une fois) et interventions (à chaque besoin).

Une habilitation crée un compte AD dormant. Chaque intervention l'ouvre sur un
créneau validé, puis il se referme. Tant que l'ouverture n'est pas automatisée
(lot 3), le portail génère des tâches pour le référent technique.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

DUREE_MAX_HABILITATION = timedelta(days=366)
DUREE_MAX_INTERVENTION = timedelta(hours=8)


class Application(models.Model):
    """Ressource accessible aux prestataires (ex. : PACS via BeyondTrust, VPN Check Point)."""

    nom = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    referents_applicatifs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="applications_referent", blank=True
    )
    groupes_ad = models.CharField(
        "groupes AD donnant l'accès",
        max_length=500,
        blank=True,
        help_text="Noms des groupes AD (VPN, BeyondTrust…), séparés par des virgules. Utilisés au lot 3.",
    )
    creation_beyondtrust = models.BooleanField(
        "création manuelle dans BeyondTrust",
        default=True,
        help_text="Une tâche est créée pour le référent technique à chaque nouvelle habilitation.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Habilitation(models.Model):
    class Statut(models.TextChoices):
        ATTENTE_CHARTE = "attente_charte", "Charte à signer"
        EN_VALIDATION = "en_validation", "En validation RSSI"
        PREPARATION = "preparation", "Compte en préparation"
        DORMANTE = "dormante", "Dormante"
        REFUSEE = "refusee", "Refusée"
        REVOQUEE = "revoquee", "Révoquée"
        EXPIREE = "expiree", "Expirée"

    class Risque(models.TextChoices):
        FAIBLE = "faible", "Faible"
        MOYEN = "moyen", "Moyen"
        ELEVE = "eleve", "Élevé"

    intervenant = models.ForeignKey("prestataires.Intervenant", on_delete=models.PROTECT, related_name="habilitations")
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="habilitations")
    referent_interne = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="habilitations_demandees")
    justification = models.TextField()
    risque = models.CharField(max_length=10, choices=Risque.choices, default=Risque.MOYEN)
    date_fin = models.DateField("fin d'habilitation")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ATTENTE_CHARTE)
    validee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    validee_le = models.DateTimeField(null=True, blank=True)
    motif_decision = models.TextField(blank=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creee_le"]

    def __str__(self):
        return f"H-{self.pk:04d} · {self.intervenant.utilisateur} · {self.application}"

    @property
    def reference(self):
        return f"H-{self.pk:04d}"

    def clean(self):
        if self.date_fin and self.date_fin > (timezone.localdate() + DUREE_MAX_HABILITATION):
            raise ValidationError({"date_fin": "Une habilitation dure un an au maximum."})
        if self.date_fin and self.date_fin < timezone.localdate():
            raise ValidationError({"date_fin": "La date de fin est passée."})

    @property
    def utilisable(self):
        return self.statut == self.Statut.DORMANTE and self.date_fin >= timezone.localdate()

    def intervention_ouverte(self):
        return self.interventions.filter(statut=Intervention.Statut.OUVERTE).first()


class Intervention(models.Model):
    class Statut(models.TextChoices):
        DEMANDEE = "demandee", "À valider"
        A_OUVRIR = "a_ouvrir", "Ouverture en attente"
        OUVERTE = "ouverte", "Accès ouvert"
        FERMEE = "fermee", "Refermé"
        REFUSEE = "refusee", "Refusée"
        ANNULEE = "annulee", "Annulée"

    habilitation = models.ForeignKey(Habilitation, on_delete=models.PROTECT, related_name="interventions")
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="interventions_demandees")
    motif = models.CharField("motif ou numéro de ticket", max_length=300)
    debut = models.DateTimeField("début du créneau")
    fin = models.DateTimeField("fin du créneau")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DEMANDEE)
    validee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    validee_le = models.DateTimeField(null=True, blank=True)
    motif_decision = models.TextField(blank=True)
    ouverte_le = models.DateTimeField(null=True, blank=True)
    fermee_le = models.DateTimeField(null=True, blank=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-debut"]

    def __str__(self):
        return f"{self.reference} · {self.habilitation.intervenant.utilisateur} · {self.motif}"

    @property
    def reference(self):
        return f"I-{self.pk:04d}"

    def clean(self):
        if self.debut and self.fin:
            if self.fin <= self.debut:
                raise ValidationError({"fin": "La fin doit être après le début."})
            if self.fin - self.debut > DUREE_MAX_INTERVENTION:
                raise ValidationError({"fin": "Un créneau dure 8 heures au maximum."})
            if self.fin < timezone.now():
                raise ValidationError({"fin": "Le créneau est déjà passé."})
            if self.habilitation_id and self.fin.date() > self.habilitation.date_fin:
                raise ValidationError({"fin": "Le créneau dépasse la fin de l'habilitation."})

    @property
    def en_retard(self):
        return self.statut == self.Statut.OUVERTE and self.fin < timezone.now()


class TacheTechnique(models.Model):
    """Action à réaliser à la main par le référent technique, puis à confirmer dans le portail."""

    class Type(models.TextChoices):
        CREATION_BEYONDTRUST = "creation_beyondtrust", "Créer le compte dans BeyondTrust"
        OUVERTURE = "ouverture", "Activer le compte AD"
        FERMETURE = "fermeture", "Désactiver le compte AD"

    type = models.CharField(max_length=30, choices=Type.choices)
    habilitation = models.ForeignKey(Habilitation, on_delete=models.PROTECT, related_name="taches")
    intervention = models.ForeignKey(Intervention, null=True, blank=True, on_delete=models.PROTECT, related_name="taches")
    a_faire_avant = models.DateTimeField(null=True, blank=True)
    faite_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    faite_le = models.DateTimeField(null=True, blank=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["faite_le", "a_faire_avant", "creee_le"]
        verbose_name = "tâche technique"

    def __str__(self):
        return f"{self.get_type_display()} · {self.habilitation}"

    @property
    def faite(self):
        return self.faite_le is not None
