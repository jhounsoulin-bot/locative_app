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


# ✅ Widget personnalisé pour mois/année
class MonthYearWidget(forms.DateInput):
    input_type = "month"


class PaiementForm(forms.ModelForm):
    proprietaire = forms.ModelChoiceField(
        queryset=Proprietaire.objects.all(),
        required=True,
        label="Propriétaire",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_proprietaire"})
    )
    locataire = forms.ModelChoiceField(
        queryset=Locataire.objects.none(),  # vide par défaut
        required=True,
        label="Locataire",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_locataire"})
    )

    class Meta:
        model = Paiement
        fields = ["proprietaire", "locataire", "date_paiement", "mois_concerne", "montant", "paye_en_avance"]
        widgets = {
            "date_paiement": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "mois_concerne": MonthYearWidget(attrs={"class": "form-control", "id": "id_mois_concerne"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "id": "id_montant"}),
            "paye_en_avance": forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_paye_en_avance"}),
        }

