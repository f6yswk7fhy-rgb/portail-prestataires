from django.urls import path

from . import views

app_name = "acces"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("habilitations/nouvelle/", views.nouvelle, name="nouvelle"),
    path("habilitations/<int:pk>/", views.detail, name="detail"),
    path("habilitations/<int:pk>/decision/", views.decider_habilitation, name="decider_habilitation"),
    path("habilitations/<int:pk>/revocation/", views.revoquer, name="revoquer"),
    path("habilitations/<int:pk>/intervention/", views.demander_intervention, name="demander_intervention"),
    path("interventions/<int:pk>/decision/", views.decider_intervention, name="decider_intervention"),
    path("interventions/<int:pk>/fermeture/", views.fermer, name="fermer"),
    path("taches/", views.taches, name="taches"),
    path("taches/<int:pk>/confirmation/", views.confirmer_tache, name="confirmer_tache"),
]
