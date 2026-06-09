from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('',                               views.login_view,         name='login'),
    path('logout/',                        views.logout_view,        name='logout'),
    path('dashboard/',                     views.dashboard,          name='dashboard'),

    # Géographie
    path('geographie/',                    views.geographie,              name='geographie'),
    path('geographie/commune/supprimer/<int:pk>/',        views.supprimer_commune,       name='supprimer_commune'),
    path('geographie/arrondissement/supprimer/<int:pk>/', views.supprimer_arrondissement,name='supprimer_arrondissement'),
    path('geographie/quartier/supprimer/<int:pk>/',       views.supprimer_quartier,      name='supprimer_quartier'),
    path('geographie/zone/supprimer/<int:pk>/',           views.supprimer_zone,          name='supprimer_zone'),

    # API AJAX
    path('api/arrondissements/<int:commune_id>/',       views.get_arrondissements, name='get_arrondissements'),
    path('api/quartiers/<int:arrondissement_id>/',      views.get_quartiers,       name='get_quartiers'),
    path('api/zones/<int:quartier_id>/',                views.get_zones,           name='get_zones'),
    path('api/terrains/<int:zone_id>/',                 views.get_terrains,        name='get_terrains'),

    # Terrains
    path('terrains/',                      views.terrains,           name='terrains'),
    path('terrains/<int:pk>/',             views.fiche_terrain,      name='fiche_terrain'),
    path('terrains/<int:pk>/supprimer/',   views.supprimer_terrain,  name='supprimer_terrain'),
    path('parcelles/generer/',             views.generer_parcelles,  name='generer_parcelles'),

    # Parcelles
    path('parcelles/',                     views.parcelles,          name='parcelles'),
    path('parcelles/<int:pk>/',            views.fiche_parcelle,     name='fiche_parcelle'),
    path('parcelles/<int:pk>/modifier/',   views.modifier_parcelle,  name='modifier_parcelle'),
    path('parcelles/<int:pk>/supprimer/',  views.supprimer_parcelle, name='supprimer_parcelle'),

    # Acheteurs
    path('acheteurs/',                     views.acheteurs,          name='acheteurs'),
    path('acheteurs/<int:pk>/supprimer/',  views.supprimer_acheteur, name='supprimer_acheteur'),

    # Ventes
    path('ventes/',                        views.ventes,             name='ventes'),
    path('ventes/<int:pk>/',               views.detail_vente,       name='detail_vente'),
    path('tranches/<int:pk>/supprimer/',   views.supprimer_tranche,  name='supprimer_tranche'),
    path('ventes/<int:vente_pk>/recu/',    views.recu_pdf,           name='recu_pdf'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)