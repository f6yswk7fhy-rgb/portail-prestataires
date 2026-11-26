"""Impose le second facteur aux prestataires.

Le personnel interne s'authentifie via Entra ID, dont la MFA est gérée par
l'accès conditionnel. Un prestataire authentifié par mot de passe n'accède à
rien tant qu'il n'a pas validé un code TOTP (ou enrôlé son application).
"""

from django.shortcuts import redirect
from django.urls import reverse

CHEMINS_LIBRES = ("/compte/mfa/", "/compte/deconnexion/", "/static/")


class MfaObligatoireMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = request.user
        if (
            u.is_authenticated
            and (u.est_prestataire or not u.entra_oid)
            and not u.is_verified()
            and not request.path.startswith(CHEMINS_LIBRES)
        ):
            return redirect(reverse("comptes:mfa"))
        return self.get_response(request)
