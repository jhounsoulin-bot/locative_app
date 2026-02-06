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
    proprietaire = forms.ModelChoiceField(
        queryset=Proprietaire.objects.all(),
        required=True,
        label="Propriétaire",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    locataire = forms.ModelChoiceField(
        queryset=Locataire.objects.none(),
        required=True,
        label="Locataire",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Paiement
        fields = ["locataire", "mois_concerne", "montant"]  # ⚠️ on enlève "proprietaire"
        widgets = {
            "mois_concerne": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "montant": forms.NumberInput(attrs={"class": "form-control"}),
        }

