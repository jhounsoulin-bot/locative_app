#!/usr/bin/env bash
set -o errexit

echo "📦 Installation des dépendances..."
pip install -r requirements.txt

echo "🧹 Nettoyage des doublons AVANT migration..."
python manage.py nettoyer_doublons

echo "🗄️  Application des migrations..."
python manage.py migrate

echo "📂 Collecte des fichiers statiques..."
python manage.py collectstatic --no-input

echo "✅ Build terminé !"