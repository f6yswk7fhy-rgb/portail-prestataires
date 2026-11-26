"""Point d'entrée unique pour écrire dans le journal d'audit."""

from django.conf import settings

from .models import EntreeAudit


def adresse_ip(request):
    """Adresse IP du client. X-Forwarded-For n'est lu que derrière un proxy de confiance."""
    if request is None:
        return None
    distante = request.META.get("REMOTE_ADDR")
    if distante in settings.PORTAIL_PROXIES_DE_CONFIANCE:
        transmise = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if transmise:
            return transmise.split(",")[-1].strip()
    return distante


def journaliser(action, *, request=None, acteur=None, objet=None, details=None):
    if acteur is None and request is not None and request.user.is_authenticated:
        acteur = request.user
    return EntreeAudit.objects.create(
        acteur=acteur,
        acteur_libelle=(acteur.get_full_name() or acteur.email) if acteur else "Système",
        action=action,
        objet_type=objet._meta.label if objet is not None else "",
        objet_id=str(objet.pk) if objet is not None else "",
        details=details or {},
        adresse_ip=adresse_ip(request),
    )
