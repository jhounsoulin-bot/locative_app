import django
from django.urls import get_resolver

django.setup()

print("Liste des URLs enregistrées :")
for pattern in get_resolver().url_patterns:
    print(pattern)
