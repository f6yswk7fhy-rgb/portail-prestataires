from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from audit.journal import journaliser


def lien_invitation(request, utilisateur):
    uid = urlsafe_base64_encode(force_bytes(utilisateur.pk))
    jeton = default_token_generator.make_token(utilisateur)
    return request.build_absolute_uri(reverse("comptes:invitation", args=[uid, jeton]))


def envoyer_invitation(request, intervenant):
    utilisateur = intervenant.utilisateur
    lien = lien_invitation(request, utilisateur)
    send_mail(
        subject=f"{settings.PORTAIL_NOM_ETABLISSEMENT} : activez votre compte prestataire",
        message=(
            f"Bonjour {utilisateur.first_name},\n\n"
            f"{settings.PORTAIL_NOM_ETABLISSEMENT} vous invite à créer votre compte sur le portail prestataires "
            f"afin de signer la charte d'utilisation du système d'information.\n\n"
            f"Lien personnel, valable {settings.INVITATION_VALIDITE_JOURS} jours :\n{lien}\n\n"
            "Vous devrez configurer une application d'authentification (Microsoft Authenticator, "
            "Google Authenticator, FreeOTP…).\n"
        ),
        from_email=None,
        recipient_list=[utilisateur.email],
    )
    journaliser("Invitation envoyée", request=request, objet=intervenant, details={"email": utilisateur.email})
