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
                "placeholder": "Loyer mensuel",
                "step": "0.01"
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
        widget=forms.Select(attrs={"class": "form-select", "id": "id_proprietaire"})
    )
    locataire = forms.ModelChoiceField(
        queryset=Locataire.objects.none(),
        required=True,
        label="Locataire",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_locataire"})
    )
    mois_concerne = forms.ChoiceField(
        choices=Paiement.MOIS_CHOICES,  # ✅ utilise uniquement les choices du modèle
        label="Mois concerné",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_mois_concerne"})
    )

    class Meta:
        model = Paiement
        fields = ["proprietaire", "locataire", "date_paiement", "mois_concerne", "montant", "paye_en_avance"]
        widgets = {
            "date_paiement": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "id": "id_montant", "step": "0.01"}),
            "paye_en_avance": forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_paye_en_avance"}),
        }

    def __init__(self, *args, **kwargs):
        proprietaire_id = kwargs.pop("proprietaire_id", None)
        super().__init__(*args, **kwargs)
        if proprietaire_id:
            self.fields["locataire"].queryset = Locataire.objects.filter(proprietaire_id=proprietaire_id)
        else:
            self.fields["locataire"].queryset = Locataire.objects.all()
