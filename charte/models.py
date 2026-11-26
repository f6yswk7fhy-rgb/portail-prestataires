import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class CharteVersion(models.Model):
    """Version de la charte. Une fois publiée, son contenu ne peut plus changer."""

    numero = models.CharField("numéro de version", max_length=20, unique=True)
    titre = models.CharField(max_length=200, default="Charte d'utilisation du SI par les prestataires")
    contenu = models.TextField(help_text="Texte intégral de la charte. Une ligne vide sépare deux paragraphes.")
    empreinte = models.CharField("empreinte SHA-256", max_length=64, editable=False)
    publiee_le = models.DateTimeField(null=True, blank=True, editable=False)
    publiee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    en_vigueur = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-publiee_le", "-id"]
        verbose_name = "version de charte"
        verbose_name_plural = "versions de charte"

    def __str__(self):
        return f"Charte v{self.numero}"

    @classmethod
    def active(cls):
        return cls.objects.filter(en_vigueur=True).first()

    @staticmethod
    def calculer_empreinte(contenu):
        return hashlib.sha256(contenu.encode("utf-8")).hexdigest()

    def clean(self):
        if self.pk:
            origine = CharteVersion.objects.get(pk=self.pk)
            if origine.publiee_le and (origine.contenu != self.contenu or origine.numero != self.numero):
                raise ValidationError("Une version publiée ne peut plus être modifiée : créez une nouvelle version.")

    def save(self, *args, **kwargs):
        self.full_clean()
        self.empreinte = self.calculer_empreinte(self.contenu)
        super().save(*args, **kwargs)

    def publier(self, par):
        with transaction.atomic():
            CharteVersion.objects.filter(en_vigueur=True).exclude(pk=self.pk).update(en_vigueur=False)
            self.en_vigueur = True
            self.publiee_le = self.publiee_le or timezone.now()
            self.publiee_par = self.publiee_par or par
            self.save()


class Signature(models.Model):
    """Preuve de signature simple : engagement explicite + code MFA, horodaté et lié à l'empreinte du texte."""

    intervenant = models.ForeignKey("prestataires.Intervenant", on_delete=models.PROTECT, related_name="signatures")
    version = models.ForeignKey(CharteVersion, on_delete=models.PROTECT, related_name="signatures")
    signee_le = models.DateTimeField(default=timezone.now, editable=False)
    empreinte_document = models.CharField(max_length=64, editable=False)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    navigateur = models.CharField(max_length=300, blank=True)
    mfa_verifiee = models.BooleanField(default=False)
    preuve = models.CharField("empreinte de la preuve", max_length=64, editable=False)

    class Meta:
        ordering = ["-signee_le"]
        constraints = [models.UniqueConstraint(fields=["intervenant", "version"], name="une_signature_par_version")]

    def __str__(self):
        return f"{self.intervenant} · v{self.version.numero} · {self.signee_le:%d/%m/%Y %H:%M}"

    def calculer_preuve(self):
        donnees = "|".join(
            [
                str(self.intervenant_id),
                self.intervenant.utilisateur.email,
                self.version.numero,
                self.empreinte_document,
                self.signee_le.isoformat(),
                self.adresse_ip or "",
                "mfa" if self.mfa_verifiee else "",
            ]
        )
        return hashlib.sha256(donnees.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Une signature ne peut pas être modifiée.")
        self.empreinte_document = self.version.empreinte
        self.preuve = self.calculer_preuve()
        super().save(*args, **kwargs)
