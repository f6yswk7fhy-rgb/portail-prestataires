from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _creer(self, email, password, **champs):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        utilisateur = self.model(email=self.normalize_email(email).lower(), **champs)
        if password:
            utilisateur.set_password(password)
        else:
            utilisateur.set_unusable_password()
        utilisateur.save(using=self._db)
        return utilisateur

    def create_user(self, email, password=None, **champs):
        champs.setdefault("is_staff", False)
        champs.setdefault("is_superuser", False)
        return self._creer(email, password, **champs)

    def create_superuser(self, email, password=None, **champs):
        champs.update(is_staff=True, is_superuser=True, type_compte=Utilisateur.Type.INTERNE)
        return self._creer(email, password, **champs)


class Utilisateur(AbstractUser):
    """Compte du portail.

    - Personnel interne : connexion SSO Entra ID, rôles issus des groupes AD.
    - Prestataire : compte local, mot de passe + TOTP obligatoire.
    """

    class Type(models.TextChoices):
        INTERNE = "interne", "Personnel interne"
        PRESTATAIRE = "prestataire", "Prestataire"

    username = None
    email = models.EmailField("adresse email", unique=True)
    type_compte = models.CharField("type de compte", max_length=20, choices=Type.choices, default=Type.PRESTATAIRE)
    entra_oid = models.CharField("identifiant Entra ID", max_length=64, blank=True, unique=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "utilisateur"

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def est_prestataire(self):
        return self.type_compte == self.Type.PRESTATAIRE
