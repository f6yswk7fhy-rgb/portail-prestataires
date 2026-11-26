"""Rôles du portail, portés par des groupes Django synchronisés depuis Entra ID / AD."""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db import models


class Role(models.TextChoices):
    RSSI = "RSSI"
    DSI = "DSI"
    REFERENT_INTERNE = "Référent interne"
    REFERENT_APPLICATIF = "Référent applicatif"
    REFERENT_TECHNIQUE = "Référent technique"


def roles_de(utilisateur):
    if not utilisateur.is_authenticated:
        return set()
    if not hasattr(utilisateur, "_roles_cache"):
        utilisateur._roles_cache = set(utilisateur.groups.filter(name__in=Role.values).values_list("name", flat=True))
    return utilisateur._roles_cache


def a_role(utilisateur, *roles):
    return bool(roles_de(utilisateur) & set(roles))


def role_requis(*roles):
    def decorateur(vue):
        @wraps(vue)
        def enveloppe(request, *args, **kwargs):
            if not a_role(request.user, *roles):
                raise PermissionDenied
            return vue(request, *args, **kwargs)

        return enveloppe

    return decorateur
