from django.contrib.auth.models import Group
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from comptes.models import Utilisateur
from prestataires.models import Intervenant, Societe


def creer_prestataire(email="thomas@exemple-presta.fr", mot_de_passe="Mot-de-passe-solide-42"):
    u = Utilisateur.objects.create_user(email=email, password=mot_de_passe, first_name="Thomas", last_name="Girard")
    societe, _ = Societe.objects.get_or_create(raison_sociale="MédiSoft")
    intervenant = Intervenant.objects.create(utilisateur=u, societe=societe)
    return u, intervenant


def ajouter_totp(utilisateur):
    return TOTPDevice.objects.create(user=utilisateur, name="test", confirmed=True)


def code_valide(appareil):
    return f"{totp(appareil.bin_key, appareil.step, appareil.t0, appareil.digits, appareil.drift):06d}"


def creer_interne(email="rssi@etablissement.fr", roles=()):
    u = Utilisateur.objects.create_user(
        email=email, type_compte=Utilisateur.Type.INTERNE, entra_oid=f"oid-{email}"
    )
    for r in roles:
        u.groups.add(Group.objects.get(name=r))
    return u
