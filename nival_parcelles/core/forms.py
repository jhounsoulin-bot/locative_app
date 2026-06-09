from django import forms
from .models import Commune, Arrondissement, Quartier, Zone, Terrain, Parcelle, Acheteur, Vente, Tranche


class CommuneForm(forms.ModelForm):
    class Meta:
        model  = Commune
        fields = ['nom']


class ArrondissementForm(forms.ModelForm):
    class Meta:
        model  = Arrondissement
        fields = ['nom', 'commune']


class QuartierForm(forms.ModelForm):
    class Meta:
        model  = Quartier
        fields = ['nom', 'arrondissement']


class ZoneForm(forms.ModelForm):
    class Meta:
        model  = Zone
        fields = ['nom', 'quartier']


class TerrainForm(forms.ModelForm):
    class Meta:
        model  = Terrain
        fields = ['reference', 'zone', 'superficie_ha', 'nb_parcelles_prevues', 'plan', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ParcelleManuelleForm(forms.ModelForm):
    class Meta:
        model  = Parcelle
        fields = ['reference', 'terrain', 'superficie_m2', 'prix_total', 'plan', 'statut']


class GenerationParcellesForm(forms.Form):
    """Génération automatique de parcelles à partir d'un terrain"""
    terrain           = forms.ModelChoiceField(queryset=Terrain.objects.all())
    nb_parcelles      = forms.IntegerField(min_value=1, label="Nombre de parcelles")
    superficie_m2     = forms.DecimalField(max_digits=10, decimal_places=2, label="Superficie par parcelle (m²)")
    prix_total        = forms.DecimalField(max_digits=15, decimal_places=2, label="Prix par parcelle (FCFA)")
    prefixe_reference = forms.CharField(max_length=20, label="Préfixe référence (ex: CAL-01-)")


class AcheteurForm(forms.ModelForm):
    class Meta:
        model  = Acheteur
        fields = ['nom', 'telephone', 'email', 'adresse']
        widgets = {'adresse': forms.Textarea(attrs={'rows': 2})}


class VenteForm(forms.ModelForm):
    class Meta:
        model  = Vente
        fields = ['parcelle', 'acheteur', 'date_vente', 'mode_paiement', 'remarque']
        widgets = {
            'date_vente': forms.DateInput(attrs={'type': 'date'}),
            'remarque':   forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parcelle'].queryset = Parcelle.objects.filter(statut__in=['disponible', 'reservee'])


class TrancheForm(forms.ModelForm):
    class Meta:
        model  = Tranche
        fields = ['montant', 'date_paiement', 'remarque']
        widgets = {
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
            'remarque':      forms.Textarea(attrs={'rows': 2}),
        }