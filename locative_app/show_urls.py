import sys
from django.conf import settings
from django.urls import get_resolver

# Assurer que Django est initialisé
import django
django.setup()

print("Liste des URLs enregistrées :\n")

resolver = get_resolver()
for pattern in resolver.url_patterns:
    print(pattern)
