from django.contrib import admin, messages

from audit.journal import journaliser

from .models import CharteVersion, Signature


@admin.register(CharteVersion)
class CharteVersionAdmin(admin.ModelAdmin):
    list_display = ("numero", "titre", "en_vigueur", "publiee_le", "nb_signatures")
    readonly_fields = ("empreinte", "publiee_le", "publiee_par", "en_vigueur")
    actions = ["action_publier"]

    def get_readonly_fields(self, request, obj=None):
        champs = list(super().get_readonly_fields(request, obj))
        if obj and obj.publiee_le:
            champs += ["numero", "titre", "contenu"]
        return champs

    def has_delete_permission(self, request, obj=None):
        return obj is None or not obj.publiee_le

    @admin.display(description="signatures")
    def nb_signatures(self, obj):
        return obj.signatures.count()

    @admin.action(description="Publier comme version en vigueur")
    def action_publier(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Sélectionnez une seule version.", messages.ERROR)
            return
        version = queryset.get()
        version.publier(request.user)
        journaliser(f"Charte v{version.numero} publiée", request=request, objet=version, details={"empreinte": version.empreinte})
        self.message_user(request, f"v{version.numero} est en vigueur : chaque intervenant devra la signer.", messages.SUCCESS)


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ("intervenant", "version", "signee_le", "mfa_verifiee", "adresse_ip")
    list_filter = ("version",)
    readonly_fields = [f.name for f in Signature._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
