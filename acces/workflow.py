"""Règles de passage d'un état à l'autre. Toute transition est contrôlée ici et journalisée.

Les vues n'écrivent jamais directement un statut : elles appellent ces fonctions,
qui vérifient le rôle de l'acteur et l'état courant.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.journal import journaliser
from charte.models import CharteVersion
from comptes.roles import Role, a_role

from .models import Habilitation, Intervention, TacheTechnique

H = Habilitation.Statut
I = Intervention.Statut


class TransitionInterdite(ValidationError):
    pass


def _exiger(condition, message):
    if not condition:
        raise TransitionInterdite(message)


def charte_signee(intervenant):
    version = CharteVersion.active()
    return version is not None and intervenant.a_signe(version)


# --- Droits ---------------------------------------------------------------

def peut_creer_habilitation(u):
    return a_role(u, Role.REFERENT_INTERNE, Role.RSSI, Role.DSI)


def peut_decider_habilitation(u):
    return a_role(u, Role.RSSI)


def est_referent_applicatif(u, application):
    return u.is_authenticated and application.referents_applicatifs.filter(pk=u.pk).exists()


def peut_demander_intervention(u, habilitation):
    if getattr(u, "intervenant", None) == habilitation.intervenant:
        return True
    return est_referent_applicatif(u, habilitation.application) or a_role(u, Role.DSI)


def validation_d_office(u, habilitation):
    """Une demande du référent applicatif ou de la DSI vaut validation."""
    return est_referent_applicatif(u, habilitation.application) or a_role(u, Role.DSI)


def peut_decider_intervention(u, intervention):
    return est_referent_applicatif(u, intervention.habilitation.application)


def peut_executer_taches(u):
    return a_role(u, Role.REFERENT_TECHNIQUE)


def peut_revoquer(u):
    return a_role(u, Role.RSSI, Role.DSI)


# --- Habilitations ---------------------------------------------------------

@transaction.atomic
def creer_habilitation(request, **champs):
    if not peut_creer_habilitation(request.user):
        raise PermissionDenied
    h = Habilitation(referent_interne=request.user, **champs)
    h.statut = H.EN_VALIDATION if charte_signee(h.intervenant) else H.ATTENTE_CHARTE
    h.full_clean()
    h.save()
    journaliser("Habilitation demandée", request=request, objet=h, details={"application": str(h.application), "fin": str(h.date_fin)})
    return h


def apres_signature(request, intervenant):
    """Appelé quand un intervenant signe la charte en vigueur."""
    for h in intervenant.habilitations.filter(statut=H.ATTENTE_CHARTE):
        h.statut = H.EN_VALIDATION
        h.save(update_fields=["statut"])
        journaliser("Habilitation transmise au RSSI (charte signée)", request=request, objet=h)


@transaction.atomic
def decider_habilitation(request, h, accepter, motif=""):
    if not peut_decider_habilitation(request.user):
        raise PermissionDenied
    _exiger(h.statut == H.EN_VALIDATION, "Cette habilitation n'est pas en attente de validation.")
    h.validee_par, h.validee_le, h.motif_decision = request.user, timezone.now(), motif
    if not accepter:
        _exiger(motif.strip(), "Un motif est obligatoire pour refuser.")
        h.statut = H.REFUSEE
        h.save()
        journaliser("Habilitation refusée", request=request, objet=h, details={"motif": motif})
        return h
    _exiger(charte_signee(h.intervenant), "L'intervenant n'a pas signé la charte en vigueur.")
    if h.application.creation_beyondtrust:
        h.statut = H.PREPARATION
        h.save()
        TacheTechnique.objects.create(type=TacheTechnique.Type.CREATION_BEYONDTRUST, habilitation=h)
        journaliser("Habilitation validée, tâche de création BeyondTrust créée", request=request, objet=h)
    else:
        h.statut = H.DORMANTE
        h.save()
        journaliser("Habilitation validée, compte dormant", request=request, objet=h)
    return h


@transaction.atomic
def revoquer(request, h, motif):
    if not peut_revoquer(request.user):
        raise PermissionDenied
    _exiger(h.statut in {H.ATTENTE_CHARTE, H.EN_VALIDATION, H.PREPARATION, H.DORMANTE}, "Habilitation déjà close.")
    _exiger(motif.strip(), "Un motif est obligatoire.")
    h.statut, h.motif_decision = H.REVOQUEE, motif
    h.save()
    for i in h.interventions.filter(statut__in=[I.DEMANDEE, I.A_OUVRIR]):
        i.statut = I.ANNULEE
        i.save(update_fields=["statut"])
    ouverte = h.intervention_ouverte()
    if ouverte:
        _fermeture_urgente(ouverte)
    journaliser("Habilitation révoquée", request=request, objet=h, details={"motif": motif})
    return h


# --- Interventions ---------------------------------------------------------

@transaction.atomic
def demander_intervention(request, h, motif, debut, fin):
    if not peut_demander_intervention(request.user, h):
        raise PermissionDenied
    _exiger(h.utilisable, "L'habilitation n'est pas active.")
    _exiger(charte_signee(h.intervenant), "L'intervenant doit d'abord signer la charte en vigueur.")
    _exiger(
        not h.interventions.filter(statut__in=[I.DEMANDEE, I.A_OUVRIR, I.OUVERTE]).exists(),
        "Une intervention est déjà en cours ou en attente pour cette habilitation.",
    )
    i = Intervention(habilitation=h, demandeur=request.user, motif=motif, debut=debut, fin=fin)
    i.full_clean()
    i.save()
    journaliser("Intervention demandée", request=request, objet=i, details={"motif": motif, "debut": str(debut), "fin": str(fin)})
    if validation_d_office(request.user, h):
        _valider(request, i, d_office=True)
    return i


def _valider(request, i, d_office=False):
    i.statut, i.validee_par, i.validee_le = I.A_OUVRIR, request.user, timezone.now()
    i.save()
    TacheTechnique.objects.create(
        type=TacheTechnique.Type.OUVERTURE, habilitation=i.habilitation, intervention=i, a_faire_avant=i.debut
    )
    journaliser(
        "Intervention validée d'office" if d_office else "Intervention validée",
        request=request,
        objet=i,
        details={"tache": "ouverture du compte AD par le référent technique"},
    )


@transaction.atomic
def decider_intervention(request, i, accepter, motif=""):
    if not peut_decider_intervention(request.user, i):
        raise PermissionDenied
    _exiger(i.statut == I.DEMANDEE, "Cette intervention n'est pas en attente de validation.")
    if accepter:
        _exiger(i.habilitation.utilisable, "L'habilitation n'est plus active.")
        _valider(request, i)
    else:
        _exiger(motif.strip(), "Un motif est obligatoire pour refuser.")
        i.statut, i.validee_par, i.validee_le, i.motif_decision = I.REFUSEE, request.user, timezone.now(), motif
        i.save()
        journaliser("Intervention refusée", request=request, objet=i, details={"motif": motif})
    return i


def _fermeture_urgente(i):
    tache = i.taches.filter(type=TacheTechnique.Type.FERMETURE, faite_le__isnull=True).first()
    if tache:
        tache.a_faire_avant = timezone.now()
        tache.save(update_fields=["a_faire_avant"])
    else:
        TacheTechnique.objects.create(
            type=TacheTechnique.Type.FERMETURE, habilitation=i.habilitation, intervention=i, a_faire_avant=timezone.now()
        )


@transaction.atomic
def fermer_maintenant(request, i):
    if not (peut_revoquer(request.user) or peut_decider_intervention(request.user, i)):
        raise PermissionDenied
    _exiger(i.statut == I.OUVERTE, "L'accès n'est pas ouvert.")
    _fermeture_urgente(i)
    journaliser("Fermeture anticipée demandée", request=request, objet=i)


# --- Tâches techniques -----------------------------------------------------

@transaction.atomic
def confirmer_tache(request, tache):
    if not peut_executer_taches(request.user):
        raise PermissionDenied
    tache = TacheTechnique.objects.select_for_update().get(pk=tache.pk)
    _exiger(not tache.faite, "Tâche déjà confirmée.")
    h, i, T = tache.habilitation, tache.intervention, TacheTechnique.Type
    if tache.type == T.CREATION_BEYONDTRUST:
        _exiger(h.statut == H.PREPARATION, "L'habilitation n'est plus en préparation.")
        h.statut = H.DORMANTE
        h.save(update_fields=["statut"])
    elif tache.type == T.OUVERTURE:
        _exiger(i.statut == I.A_OUVRIR, "L'intervention n'est plus à ouvrir.")
        _exiger(h.statut == H.DORMANTE, "L'habilitation n'est plus active.")
        i.statut, i.ouverte_le = I.OUVERTE, timezone.now()
        i.save(update_fields=["statut", "ouverte_le"])
        TacheTechnique.objects.create(type=T.FERMETURE, habilitation=h, intervention=i, a_faire_avant=i.fin)
    elif tache.type == T.FERMETURE:
        i.statut, i.fermee_le = I.FERMEE, timezone.now()
        i.save(update_fields=["statut", "fermee_le"])
    tache.faite_par, tache.faite_le = request.user, timezone.now()
    tache.save(update_fields=["faite_par", "faite_le"])
    journaliser(f"Tâche confirmée : {tache.get_type_display()}", request=request, objet=tache.intervention or h)
    return tache


def taches_en_attente():
    """Tâches à faire, hors ouvertures annulées entre-temps."""
    return (
        TacheTechnique.objects.filter(faite_le__isnull=True)
        .exclude(type=TacheTechnique.Type.OUVERTURE, intervention__statut__in=[I.ANNULEE, I.REFUSEE])
        .exclude(type=TacheTechnique.Type.CREATION_BEYONDTRUST, habilitation__statut__in=[H.REVOQUEE, H.REFUSEE])
        .select_related("habilitation__intervenant__utilisateur", "habilitation__application", "intervention")
    )
