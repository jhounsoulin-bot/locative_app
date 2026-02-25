"""
Script à exécuter UNE SEULE FOIS pour créer le premier compte admin.
Lancez : python create_admin.py

Placez ce fichier à la racine de votre projet Django (là où manage.py se trouve).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locative_app.settings')  # ← adaptez si nécessaire
django.setup()

from core.models import AdminCompte  # ← adaptez selon votre app

username = input("Choisissez un nom d'utilisateur : ").strip()
password = input("Choisissez un mot de passe : ").strip()

if AdminCompte.objects.exists():
    print("⚠️  Un compte existe déjà. Supprimez-le d'abord si vous voulez le recréer.")
else:
    compte = AdminCompte(username=username)
    compte.set_password(password)
    compte.save()
    print(f"✅ Compte '{username}' créé avec succès !")