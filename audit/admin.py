from django.contrib import admin

from .models import EntreeAudit


@admin.register(EntreeAudit)
class EntreeAuditAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "acteur_libelle", "action", "objet_type", "objet_id", "adresse_ip")
    list_filter = ("action", "objet_type")
    search_fields = ("acteur_libelle", "action", "objet_id")
    readonly_fields = [f.name for f in EntreeAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
