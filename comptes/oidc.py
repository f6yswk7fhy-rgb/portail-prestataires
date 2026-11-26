"""Connexion SSO du personnel via Entra ID (OpenID Connect).

Les rôles du portail sont recalculés à chaque connexion à partir de la
revendication « groups » du jeton (identifiants des groupes AD synchronisés),
selon la table OIDC_GROUPES_ROLES. Un compte prestataire ne peut jamais se
connecter par cette voie.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from audit.journal import journaliser

from .roles import Role


class EntraIdBackend(OIDCAuthenticationBackend):
    def get_userinfo(self, access_token, id_token, payload):
        infos = super().get_userinfo(access_token, id_token, payload)
        # Les groupes et l'oid figurent dans le jeton d'identité, pas toujours dans userinfo.
        infos.setdefault("groups", payload.get("groups", []))
        infos.setdefault("oid", payload.get("oid"))
        infos.setdefault("email", payload.get("email") or payload.get("preferred_username"))
        return infos

    def filter_users_by_claims(self, claims):
        oid = claims.get("oid")
        if oid:
            par_oid = self.UserModel.objects.filter(entra_oid=oid)
            if par_oid.exists():
                return par_oid
        email = (claims.get("email") or "").lower()
        return self.UserModel.objects.filter(email=email, type_compte=self.UserModel.Type.INTERNE)

    def create_user(self, claims):
        utilisateur = self.UserModel.objects.create_user(
            email=claims.get("email"),
            first_name=claims.get("given_name", ""),
            last_name=claims.get("family_name", ""),
            type_compte=self.UserModel.Type.INTERNE,
            entra_oid=claims.get("oid"),
        )
        self.synchroniser_roles(utilisateur, claims)
        journaliser("Compte interne créé via Entra ID", acteur=utilisateur, objet=utilisateur)
        return utilisateur

    def update_user(self, utilisateur, claims):
        if utilisateur.est_prestataire:
            return None
        utilisateur.first_name = claims.get("given_name", utilisateur.first_name)
        utilisateur.last_name = claims.get("family_name", utilisateur.last_name)
        utilisateur.entra_oid = utilisateur.entra_oid or claims.get("oid")
        utilisateur.save(update_fields=["first_name", "last_name", "entra_oid"])
        self.synchroniser_roles(utilisateur, claims)
        return utilisateur

    def verify_claims(self, claims):
        return bool(claims.get("email")) and bool(claims.get("oid"))

    @staticmethod
    def synchroniser_roles(utilisateur, claims):
        voulus = {settings.OIDC_GROUPES_ROLES[g] for g in claims.get("groups", []) if g in settings.OIDC_GROUPES_ROLES}
        voulus &= set(Role.values)
        actuels = set(utilisateur.groups.filter(name__in=Role.values).values_list("name", flat=True))
        if voulus == actuels:
            return
        for nom in actuels - voulus:
            utilisateur.groups.remove(Group.objects.get(name=nom))
        for nom in voulus - actuels:
            utilisateur.groups.add(Group.objects.get_or_create(name=nom)[0])
        journaliser(
            "Rôles synchronisés depuis Entra ID",
            acteur=utilisateur,
            objet=utilisateur,
            details={"avant": sorted(actuels), "apres": sorted(voulus)},
        )
