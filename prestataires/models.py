from django.conf import settings
from django.db import models


class Societe(models.Model):
    raison_sociale = models.CharField(max_length=200, unique=True)
    siret = models.CharField("SIRET", max_length=14, blank=True)
    contact_nom = models.CharField("responsable côté prestataire", max_length=200, blank=True)
    contact_email = models.EmailField("email du responsable", blank=True)
    active = models.BooleanField(default=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["raison_sociale"]
        verbose_name = "société prestataire"
        verbose_name_plural = "sociétés prestataires"

    def __str__(self):
        return self.raison_sociale


class Intervenant(models.Model):
    class Statut(models.TextChoices):
        INVITE = "invite", "Invité"
        ACTIF = "actif", "Actif"
        SUSPENDU = "suspendu", "Suspendu"
        PARTI = "parti", "Parti"

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intervenant")
    societe = models.ForeignKey(Societe, on_delete=models.PROTECT, related_name="intervenants")
    telephone = models.CharField(max_length=30, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.INVITE)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["utilisateur__last_name", "utilisateur__first_name"]

    def __str__(self):
        return f"{self.utilisateur} ({self.societe})"

    def a_signe(self, version):
        return self.signatures.filter(version=version).exists()
