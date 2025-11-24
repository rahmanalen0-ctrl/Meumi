release: cd backend && python manage.py migrate
web: cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
