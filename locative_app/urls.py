from django.contrib import admin
from django.urls import path
from core import views   # importer toutes les vues de ton app core

urlpatterns = [
    # Administration
    path("admin/", admin.site.urls),

    # Page d’accueil
    path("", views.accueil, name="accueil"),

    # Paiements
    path("paiements/", views.liste_paiements, name="liste_paiements"),
    path("ajouter-paiement/", views.ajouter_paiement, name="ajouter_paiement"),

    # Propriétaires
    path("ajouter-proprietaire/", views.ajouter_proprietaire, name="ajouter_proprietaire"),
    path("proprietaire/modifier/<int:pk>/", views.modifier_proprietaire, name="modifier_proprietaire"),
    path("proprietaire/supprimer/<int:pk>/", views.supprimer_proprietaire, name="supprimer_proprietaire"),

    # Locataires
    path("ajouter-locataire/", views.ajouter_locataire, name="ajouter_locataire"),
    path("locataire/modifier/<int:pk>/", views.modifier_locataire, name="modifier_locataire"),
    path("locataire/supprimer/<int:pk>/", views.supprimer_locataire, name="supprimer_locataire"),

    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard-pdf/", views.dashboard_pdf, name="dashboard_pdf"),

    # Factures et rapports
    path("facture/<int:proprietaire_id>/", views.facture_proprietaire, name="facture_proprietaire"),
    path("rapport-proprietaire/<int:proprietaire_id>/", views.rapport_proprietaire, name="rapport_proprietaire"),
    path("rapport-proprietaire-pdf/<int:proprietaire_id>/", views.rapport_proprietaire_pdf, name="rapport_proprietaire_pdf"),
    path("rapport-global/", views.rapport_global, name="rapport_global"),
    path("rapport-global-pdf/", views.rapport_global_pdf, name="rapport_global_pdf"),

    # API internes
    path("get-locataires/<int:proprietaire_id>/", views.get_locataires, name="get_locataires"),
    path("get-loyer/<int:locataire_id>/", views.get_loyer, name="get_loyer"),
]
