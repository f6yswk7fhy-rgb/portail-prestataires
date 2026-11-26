from django.contrib import admin
from django.urls import include, path
from django_otp.admin import OTPAdminSite

from comptes import views as comptes_views

# L'administration Django exige elle aussi un second facteur.
admin.site.__class__ = OTPAdminSite
admin.site.site_header = "Portail prestataires · administration"
admin.site.site_title = "Portail prestataires"

urlpatterns = [
    path("", comptes_views.accueil, name="accueil"),
    path("compte/", include("comptes.urls")),
    path("charte/", include("charte.urls")),
    path("audit/", include("audit.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("admin/", admin.site.urls),
]
