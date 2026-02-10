from django.contrib import admin
from django.urls import path
from core import views   # importer le module views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.accueil, name="accueil"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("ajouter-proprietaire/", views.ajouter_proprietaire, name="ajouter_proprietaire"),
    path("ajouter-locataire/", views.ajouter_locataire, name="ajouter_locataire"),
    path("ajouter-paiement/", views.ajouter_paiement, name="ajouter_paiement"),
    path("facture/<int:proprietaire_id>/", views.facture_proprietaire, name="facture_proprietaire"),
    path("dashboard-pdf/", views.dashboard_pdf, name="dashboard_pdf"),
    path("rapport-proprietaire/<int:proprietaire_id>/", views.rapport_proprietaire, name="rapport_proprietaire"),
    path("rapport-proprietaire-pdf/<int:proprietaire_id>/", views.rapport_proprietaire_pdf, name="rapport_proprietaire_pdf"),  # ✅ nouvelle route
    path("get-locataires-nom/<str:proprietaire_nom>/", views.get_locataires_by_proprietaire_nom, name="get_locataires_nom"),
    path("get-loyer/<int:locataire_id>/", views.get_loyer_locataire, name="get_loyer_locataire"),

    # ✅ routes pour modification/suppression
    path("proprietaire/modifier/<int:pk>/", views.modifier_proprietaire, name="modifier_proprietaire"),
    path("proprietaire/supprimer/<int:pk>/", views.supprimer_proprietaire, name="supprimer_proprietaire"),
    path("locataire/modifier/<int:pk>/", views.modifier_locataire, name="modifier_locataire"),
    path("locataire/supprimer/<int:pk>/", views.supprimer_locataire, name="supprimer_locataire"),
]
