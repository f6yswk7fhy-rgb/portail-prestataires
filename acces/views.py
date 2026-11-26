from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from comptes.models import Utilisateur
from comptes.roles import Role, a_role
from prestataires.invitations import envoyer_invitation
from prestataires.models import Intervenant, Societe

from . import workflow as wf
from .forms import HabilitationForm, InterventionForm, MotifForm
from .models import Habilitation, Intervention, TacheTechnique


def _message_erreur(e):
    return " ".join(e.messages) if hasattr(e, "messages") else str(e)


def habilitations_visibles(u):
    qs = Habilitation.objects.select_related("intervenant__utilisateur", "intervenant__societe", "application")
    if a_role(u, Role.RSSI, Role.DSI):
        return qs
    if getattr(u, "intervenant", None):
        return qs.filter(intervenant=u.intervenant)
    return qs.filter(Q(referent_interne=u) | Q(application__referents_applicatifs=u)).distinct()


@login_required
def liste(request):
    u = request.user
    habs = habilitations_visibles(u)
    a_valider = Intervention.objects.none()
    if not u.est_prestataire:
        a_valider = Intervention.objects.filter(
            statut=Intervention.Statut.DEMANDEE, habilitation__application__referents_applicatifs=u
        ).select_related("habilitation__intervenant__utilisateur", "habilitation__application")
    ouvertes = Intervention.objects.filter(
        statut=Intervention.Statut.OUVERTE, habilitation__in=habs
    ).select_related("habilitation__intervenant__utilisateur", "habilitation__application")
    return render(
        request,
        "acces/liste.html",
        {
            "habilitations": habs,
            "a_valider_rssi": habs.filter(statut=Habilitation.Statut.EN_VALIDATION) if wf.peut_decider_habilitation(u) else [],
            "interventions_a_valider": a_valider,
            "ouvertes": ouvertes,
            "peut_creer": wf.peut_creer_habilitation(u),
        },
    )


@login_required
def nouvelle(request):
    if not wf.peut_creer_habilitation(request.user):
        raise PermissionDenied
    form = HabilitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                intervenant, invite = _intervenant(request, d)
                h = wf.creer_habilitation(
                    request,
                    intervenant=intervenant,
                    application=d["application"],
                    risque=d["risque"],
                    date_fin=d["date_fin"],
                    justification=d["justification"],
                )
        except ValidationError as e:
            form.add_error(None, _message_erreur(e))
        else:
            if invite:
                envoyer_invitation(request, intervenant)
                messages.success(request, f"{h.reference} créée. Invitation envoyée à {intervenant.utilisateur.email}.")
            else:
                messages.success(request, f"{h.reference} créée pour {intervenant.utilisateur}.")
            return redirect("acces:detail", pk=h.pk)
    return render(request, "acces/nouvelle.html", {"form": form})


def _intervenant(request, d):
    """Retrouve l'intervenant par email, ou le crée avec son compte prestataire."""
    utilisateur = Utilisateur.objects.filter(email=d["email"]).first()
    if utilisateur:
        if not utilisateur.est_prestataire or not hasattr(utilisateur, "intervenant"):
            raise ValidationError("Cette adresse appartient à un compte qui n'est pas un intervenant prestataire.")
        return utilisateur.intervenant, False
    societe = d["societe"] or Societe.objects.get_or_create(raison_sociale=d["nouvelle_societe"].strip())[0]
    utilisateur = Utilisateur.objects.create_user(email=d["email"], first_name=d["prenom"], last_name=d["nom"])
    return Intervenant.objects.create(utilisateur=utilisateur, societe=societe), True


@login_required
def detail(request, pk):
    h = get_object_or_404(habilitations_visibles(request.user), pk=pk)
    u = request.user
    return render(
        request,
        "acces/detail.html",
        {
            "h": h,
            "interventions": h.interventions.select_related("demandeur"),
            "peut_decider": wf.peut_decider_habilitation(u) and h.statut == Habilitation.Statut.EN_VALIDATION,
            "peut_revoquer": wf.peut_revoquer(u) and h.statut not in {"refusee", "revoquee", "expiree"},
            "peut_demander": wf.peut_demander_intervention(u, h) and h.utilisable and not h.interventions.filter(
                statut__in=["demandee", "a_ouvrir", "ouverte"]
            ).exists(),
            "validation_d_office": wf.validation_d_office(u, h),
            "form_intervention": InterventionForm(),
            "form_motif": MotifForm(),
        },
    )


def _action(request, fonction, *args):
    try:
        fonction(request, *args)
    except ValidationError as e:
        messages.error(request, _message_erreur(e))
        return False
    return True


@login_required
@require_POST
def decider_habilitation(request, pk):
    h = get_object_or_404(Habilitation, pk=pk)
    accepter = request.POST.get("decision") == "valider"
    if _action(request, wf.decider_habilitation, h, accepter, request.POST.get("motif", "")):
        messages.success(request, f"{h.reference} {'validée' if accepter else 'refusée'}.")
    return redirect("acces:detail", pk=pk)


@login_required
@require_POST
def revoquer(request, pk):
    h = get_object_or_404(Habilitation, pk=pk)
    if _action(request, wf.revoquer, h, request.POST.get("motif", "")):
        messages.success(request, f"{h.reference} révoquée.")
    return redirect("acces:detail", pk=pk)


@login_required
@require_POST
def demander_intervention(request, pk):
    h = get_object_or_404(habilitations_visibles(request.user), pk=pk)
    form = InterventionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Créneau ou motif invalide.")
    else:
        d = form.cleaned_data
        if _action(request, wf.demander_intervention, h, d["motif"], d["debut"], d["fin"]):
            messages.success(request, "Intervention enregistrée.")
    return redirect("acces:detail", pk=pk)


@login_required
@require_POST
def decider_intervention(request, pk):
    i = get_object_or_404(Intervention, pk=pk)
    accepter = request.POST.get("decision") == "valider"
    if _action(request, wf.decider_intervention, i, accepter, request.POST.get("motif", "")):
        messages.success(request, f"{i.reference} {'validée' if accepter else 'refusée'}.")
    if request.POST.get("retour") == "detail":
        return redirect("acces:detail", pk=i.habilitation_id)
    return redirect("acces:liste")


@login_required
@require_POST
def fermer(request, pk):
    i = get_object_or_404(Intervention, pk=pk)
    if _action(request, wf.fermer_maintenant, i):
        messages.success(request, "Fermeture demandée au référent technique.")
    return redirect("acces:detail", pk=i.habilitation_id)


@login_required
def taches(request):
    if not wf.peut_executer_taches(request.user):
        raise PermissionDenied
    faites = TacheTechnique.objects.filter(faite_le__isnull=False).select_related(
        "habilitation__intervenant__utilisateur", "habilitation__application", "intervention", "faite_par"
    ).order_by("-faite_le")[:20]
    return render(request, "acces/taches.html", {"a_faire": wf.taches_en_attente(), "faites": faites})


@login_required
@require_POST
def confirmer_tache(request, pk):
    tache = get_object_or_404(TacheTechnique, pk=pk)
    if _action(request, wf.confirmer_tache, tache):
        messages.success(request, f"Confirmé : {tache.get_type_display().lower()}.")
    return redirect("acces:taches")
