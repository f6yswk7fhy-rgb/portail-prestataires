from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django_otp.plugins.otp_totp.models import TOTPDevice

from audit.journal import adresse_ip, journaliser

from .models import CharteVersion, Signature


class SignatureForm(forms.Form):
    engagement = forms.BooleanField(
        label="J'ai lu l'intégralité de la charte et je m'engage à la respecter.",
        error_messages={"required": "Vous devez cocher l'engagement pour signer."},
    )
    code = forms.CharField(
        label="Code de votre application d'authentification",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )


@login_required
def signer(request):
    intervenant = getattr(request.user, "intervenant", None)
    if intervenant is None:
        raise PermissionDenied
    version = CharteVersion.active()
    if version is None:
        return render(request, "charte/aucune.html")
    if intervenant.a_signe(version):
        signature = intervenant.signatures.get(version=version)
        return render(request, "charte/signee.html", {"version": version, "signature": signature})

    form = SignatureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        appareil = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
        if appareil is None or not appareil.verify_token(form.cleaned_data["code"]):
            journaliser("Signature refusée : code MFA invalide", request=request, objet=version)
            form.add_error("code", "Code invalide ou expiré.")
        else:
            try:
                signature = Signature.objects.create(
                    intervenant=intervenant,
                    version=version,
                    adresse_ip=adresse_ip(request),
                    navigateur=request.META.get("HTTP_USER_AGENT", "")[:300],
                    mfa_verifiee=True,
                )
            except IntegrityError:
                return redirect("charte:signer")
            journaliser(
                f"Charte v{version.numero} signée",
                request=request,
                objet=signature,
                details={"empreinte_document": signature.empreinte_document, "preuve": signature.preuve},
            )
            messages.success(request, f"Charte v{version.numero} signée.")
            return redirect("charte:signer")

    paragraphes = [p.strip() for p in version.contenu.split("\n\n") if p.strip()]
    return render(request, "charte/signer.html", {"version": version, "paragraphes": paragraphes, "form": form})
