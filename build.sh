#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Initialize fresh database state with primary Boss account (boss / boss123)
python manage.py clean_data
