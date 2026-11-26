from django.urls import path

from . import views

app_name = "comptes"
urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("mfa/", views.mfa, name="mfa"),
    path("invitation/<uidb64>/<jeton>/", views.invitation, name="invitation"),
]
