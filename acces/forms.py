from datetime import timedelta

from django import forms
from django.utils import timezone

from prestataires.models import Societe

from .models import Application, Habilitation


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class HabilitationForm(forms.Form):
    email = forms.EmailField(label="Email professionnel de l'intervenant")
    prenom = forms.CharField(label="Prénom", max_length=150)
    nom = forms.CharField(label="Nom", max_length=150)
    societe = forms.ModelChoiceField(label="Société", queryset=Societe.objects.filter(active=True), required=False)
    nouvelle_societe = forms.CharField(label="ou nouvelle société", max_length=200, required=False)
    application = forms.ModelChoiceField(queryset=Application.objects.filter(active=True))
    risque = forms.ChoiceField(choices=Habilitation.Risque.choices, initial=Habilitation.Risque.MOYEN)
    date_fin = forms.DateField(label="Fin d'habilitation (1 an maximum)", widget=DateInput)
    justification = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_fin"].initial = timezone.localdate() + timedelta(days=180)

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean(self):
        donnees = super().clean()
        if not donnees.get("societe") and not (donnees.get("nouvelle_societe") or "").strip():
            self.add_error("societe", "Choisissez une société ou saisissez-en une nouvelle.")
        return donnees


class InterventionForm(forms.Form):
    motif = forms.CharField(label="Motif ou numéro de ticket", max_length=300)
    debut = forms.DateTimeField(label="Début", widget=DateTimeInput)
    fin = forms.DateTimeField(label="Fin (8 heures maximum)", widget=DateTimeInput)


class MotifForm(forms.Form):
    motif = forms.CharField(label="Motif", required=False, widget=forms.Textarea(attrs={"rows": 2}))
