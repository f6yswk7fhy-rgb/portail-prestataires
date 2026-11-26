from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "type_compte", "is_active")
    list_filter = ("type_compte", "is_active", "groups")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password", "type_compte", "entra_oid")}),
        ("Identité", {"fields": ("first_name", "last_name")}),
        ("Droits", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "type_compte", "password1", "password2")}),)
    readonly_fields = ("entra_oid", "last_login", "date_joined")
