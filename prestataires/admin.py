from django.contrib import admin, messages

from .invitations import envoyer_invitation
from .models import Intervenant, Societe


@admin.register(Societe)
class SocieteAdmin(admin.ModelAdmin):
    list_display = ("raison_sociale", "siret", "contact_nom", "active")
    search_fields = ("raison_sociale", "siret")


@admin.register(Intervenant)
class IntervenantAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "societe", "statut", "cree_le")
    list_filter = ("statut", "societe")
    search_fields = ("utilisateur__email", "utilisateur__last_name")
    autocomplete_fields = ("societe",)
    actions = ["action_inviter"]

    @admin.action(description="Envoyer l'invitation par email")
    def action_inviter(self, request, queryset):
        for intervenant in queryset.select_related("utilisateur"):
            envoyer_invitation(request, intervenant)
        self.message_user(request, f"{queryset.count()} invitation(s) envoyée(s).", messages.SUCCESS)
