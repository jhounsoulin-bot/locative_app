from django.contrib import admin
from django.urls import path
from core.views import (
    accueil, dashboard, ajouter_proprietaire, ajouter_locataire, ajouter_paiement,
    facture_proprietaire, dashboard_pdf,
    modifier_proprietaire, supprimer_proprietaire,
    modifier_locataire, supprimer_locataire
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", accueil, name="accueil"),
    path("dashboard/", dashboard, name="dashboard"),
    path("ajouter-proprietaire/", ajouter_proprietaire, name="ajouter_proprietaire"),
    path("ajouter-locataire/", ajouter_locataire, name="ajouter_locataire"),
    path("ajouter-paiement/", ajouter_paiement, name="ajouter_paiement"),
    path("facture/<int:proprietaire_id>/", facture_proprietaire, name="facture_proprietaire"),
    path("dashboard-pdf/", dashboard_pdf, name="dashboard_pdf"),

    # ✅ ici aussi Django trouve bien les routes
    path("proprietaire/modifier/<int:pk>/", modifier_proprietaire, name="modifier_proprietaire"),
    path("proprietaire/supprimer/<int:pk>/", supprimer_proprietaire, name="supprimer_proprietaire"),
    path("locataire/modifier/<int:pk>/", modifier_locataire, name="modifier_locataire"),
    path("locataire/supprimer/<int:pk>/", supprimer_locataire, name="supprimer_locataire"),
]









