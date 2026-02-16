#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r locative_app/requirements.txt
python manage.py nettoyer_doublons
python manage.py migrate
python manage.py collectstatic --noinput
