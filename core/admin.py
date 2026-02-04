from django.contrib import admin
from .models import Ville
from .models import Proprietaire
from .models import Locataire
from .models import Paiement



admin.site.register(Ville)
admin.site.register(Proprietaire)
admin.site.register(Locataire)
admin.site.register(Paiement)


# Personnalisation de l'interface d'administration
admin.site.site_header = " NIVAL IMPACT"
admin.site.site_title = "NIVAL IMPACT"
admin.site.index_title = " NIVAL IMPACT"
