from django.contrib import admin

from .models import Application, Habilitation, Intervention, TacheTechnique


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("nom", "creation_beyondtrust", "active")
    filter_horizontal = ("referents_applicatifs",)
    search_fields = ("nom",)


class LectureSeuleMixin:
    """Les statuts ne se modifient que par le workflow du portail, pour garder l'audit cohérent."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Habilitation)
class HabilitationAdmin(LectureSeuleMixin, admin.ModelAdmin):
    list_display = ("reference", "intervenant", "application", "statut", "date_fin")
    list_filter = ("statut", "application")


@admin.register(Intervention)
class InterventionAdmin(LectureSeuleMixin, admin.ModelAdmin):
    list_display = ("reference", "habilitation", "motif", "debut", "fin", "statut")
    list_filter = ("statut",)


@admin.register(TacheTechnique)
class TacheTechniqueAdmin(LectureSeuleMixin, admin.ModelAdmin):
    list_display = ("type", "habilitation", "a_faire_avant", "faite_par", "faite_le")
    list_filter = ("type",)
