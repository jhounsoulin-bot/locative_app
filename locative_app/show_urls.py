import os
import django
from django.urls import get_resolver

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "locative_app.settings")
django.setup()

def list_patterns(patterns, prefix=""):
    for p in patterns:
        if hasattr(p, "url_patterns"):  # include()
            list_patterns(p.url_patterns, prefix + str(p.pattern))
        else:
            print(f"{prefix}{p.pattern} -> {p.callback}")

print("Liste des URLs enregistrées :\n")
list_patterns(get_resolver().url_patterns)
