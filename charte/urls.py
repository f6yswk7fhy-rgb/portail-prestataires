from django.urls import path

from . import views

app_name = "charte"
urlpatterns = [path("", views.signer, name="signer")]
