import base64
from io import BytesIO

import qrcode
import qrcode.image.svg
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from audit.journal import journaliser

from .models import Utilisateur


class ConnexionView(auth_views.LoginView):
    template_name = "comptes/connexion.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sso_actif"] = bool(settings.OIDC_RP_CLIENT_ID)
        return ctx

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser("Connexion par mot de passe (premier facteur)", request=self.request, objet=self.request.user)
        return reponse

    def form_invalid(self, form):
        email = (form.data.get("username") or "")[:200]
        journaliser("Échec de connexion", request=self.request, details={"email": email})
        return super().form_invalid(form)


@require_POST
def deconnexion(request):
    if request.user.is_authenticated:
        journaliser("Déconnexion", request=request, objet=request.user)
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


class CodeForm(forms.Form):
    code = forms.CharField(
        label="Code à 6 chiffres",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True}),
    )


def _qr_svg(url):
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    tampon = BytesIO()
    image.save(tampon)
    return "data:image/svg+xml;base64," + base64.b64encode(tampon.getvalue()).decode()


@login_required
def mfa(request):
    """Vérifie le code TOTP, ou enrôle l'application d'authentification au premier passage."""
    if request.user.is_verified():
        return redirect("accueil")
    appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    enrolement = appareil is None
    if enrolement:
        appareil, _ = TOTPDevice.objects.get_or_create(
            user=request.user, confirmed=False, defaults={"name": "Application d'authentification"}
        )
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if appareil.verify_token(form.cleaned_data["code"]):
            if enrolement:
                appareil.confirmed = True
                appareil.save(update_fields=["confirmed"])
                journaliser("MFA enrôlée (TOTP)", request=request, objet=request.user)
            otp_login(request, appareil)
            journaliser("Second facteur validé", request=request, objet=request.user)
            return redirect(request.GET.get("next") or "accueil")
        journaliser("Code MFA invalide", request=request, objet=request.user)
        form.add_error("code", "Code invalide ou expiré.")
    contexte = {"form": form, "enrolement": enrolement}
    if enrolement:
        contexte["qr"] = _qr_svg(appareil.config_url)
        contexte["cle"] = base64.b32encode(appareil.bin_key).decode()
    return render(request, "comptes/mfa.html", contexte)


def invitation(request, uidb64, jeton):
    """Lien d'invitation : le prestataire choisit son mot de passe, puis enrôle sa MFA."""
    try:
        utilisateur = Utilisateur.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)), type_compte="prestataire")
    except (Utilisateur.DoesNotExist, ValueError, TypeError, OverflowError):
        utilisateur = None
    if utilisateur is None or not default_token_generator.check_token(utilisateur, jeton):
        return render(request, "comptes/invitation_invalide.html", status=400)
    form = SetPasswordForm(utilisateur, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        journaliser("Mot de passe initial défini via invitation", request=request, acteur=utilisateur, objet=utilisateur)
        auth_login(request, utilisateur, backend="django.contrib.auth.backends.ModelBackend")
        messages.info(request, "Mot de passe enregistré. Configurez maintenant votre application d'authentification.")
        return redirect("comptes:mfa")
    return render(request, "comptes/invitation.html", {"form": form, "utilisateur": utilisateur})


@login_required
def accueil(request):
    contexte = {}
    if request.user.est_prestataire:
        from charte.models import CharteVersion

        intervenant = getattr(request.user, "intervenant", None)
        version = CharteVersion.active()
        contexte.update(
            intervenant=intervenant,
            version=version,
            a_signe=bool(intervenant and version and intervenant.a_signe(version)),
        )
    return render(request, "accueil.html", contexte)
