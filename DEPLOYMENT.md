# Messaging App - Render Deployment Guide

## Overview
Lightweight messaging app with Django backend and vanilla JS frontend. Features include:
- Direct messaging (1-to-1)
- Group chat with privacy levels
- File upload (up to 1GB)
- Message auto-delete after 3 hours
- Username-only authentication

## Deployment to Render

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/messaging-app.git
git push -u origin main
```

### Step 2: Create Render Account & Service
1. Go to [render.com](https://render.com)
2. Sign up and connect your GitHub account
3. Create new Web Service
4. Select your repository
5. Configure:
   - **Name**: messaging-app
   - **Environment**: Python 3
   - **Build Command**: `chmod +x build.sh && ./build.sh`
   - **Start Command**: `cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
   - **Plan**: Free (or Pro for production)

### Step 3: Add Environment Variables
In Render dashboard, go to Environment and add:

```
DEBUG=False
SECRET_KEY=<generate-a-random-string>
ALLOWED_HOSTS=yourdomain.onrender.com
CORS_ALLOWED_ORIGINS=https://yourdomain.onrender.com
```

### Step 4: Create PostgreSQL Database (Optional)
For production, use PostgreSQL instead of SQLite:

1. In Render dashboard, create new PostgreSQL database
2. Copy connection string
3. Add to environment variables as `DATABASE_URL`

### Step 5: Deploy
1. Trigger deployment via GitHub push or manual deploy in Render dashboard
2. Wait for build to complete
3. Check logs for errors

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
cd backend
python manage.py migrate

# Start server
python manage.py runserver

# Access at http://localhost:8000
```

## Project Structure
```
messaging_app/
├── backend/           # Django project
│   ├── chat/         # Main app
│   ├── config/       # Settings
│   └── manage.py
├── frontend/         # Static files
│   ├── static/       # CSS, JS
│   └── templates/    # HTML
├── requirements.txt
└── Procfile
```

## Troubleshooting

**Static files not loading:**
- Ensure `python manage.py collectstatic` runs during build
- Check `STATICFILES_DIRS` and `STATIC_ROOT` in settings.py

**Database errors:**
- If using SQLite, ensure it's in `BASE_DIR`
- If using PostgreSQL, verify `DATABASE_URL` env variable

**CORS errors:**
- Update `CORS_ALLOWED_ORIGINS` with your Render domain
- Frontend must be on same domain or CORS must allow it

**Module not found errors:**
- Ensure all requirements are in `requirements.txt`
- Check Python version matches `runtime.txt`
