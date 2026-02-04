from django import forms
from .models import Proprietaire, Locataire, Paiement

class ProprietaireForm(forms.ModelForm):
    class Meta:
        model = Proprietaire
        fields = ["nom", "numero"]
        widgets = {
            "nom": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nom du propriétaire"
            }),
            "numero": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Numéro de téléphone"
            }),
        }

class LocataireForm(forms.ModelForm):
    class Meta:
        model = Locataire
        fields = ["nom", "numero", "loyer_mensuel", "proprietaire"]
        widgets = {
            "nom": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nom du locataire"
            }),
            "numero": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Numéro de téléphone"
            }),
            "loyer_mensuel": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Loyer mensuel"
            }),
            "proprietaire": forms.Select(attrs={
                "class": "form-select"
            }),
        }

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ["locataire", "montant", "date_paiement", "mois_concerne", "en_avance"]
        widgets = {
            "locataire": forms.Select(attrs={
                "class": "form-select"
            }),
            "montant": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Montant payé"
            }),
            "date_paiement": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "mois_concerne": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "en_avance": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }
