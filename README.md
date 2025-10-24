# VTS Training Management System

A comprehensive Django-based training management system for Vetri Training Solutions.

## Features

- **Admin Dashboard**: Complete course and trainee management
- **Trainer Portal**: Attendance tracking, session management, announcements
- **Student Portal**: Course progress, attendance overview, certificates
- **Course Management**: Create, edit, and manage training courses
- **Attendance System**: Mark and track trainee attendance
- **Session Recordings**: Upload and manage training session videos
- **Certificate Generation**: Automatic certificate creation with verification
- **Responsive Design**: Mobile-friendly interface

## Local Development

### Prerequisites
- Python 3.11+
- pip
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd VTSTRAINING_CORRECTION-main
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create superuser:
```bash
python manage.py createsuperuser
```

6. Run development server:
```bash
python manage.py runserver
```

7. Access the application:
   - Admin: http://127.0.0.1:8000/admin/
   - Main site: http://127.0.0.1:8000/

## Render Deployment

### Prerequisites
- GitHub repository
- Render account

### Deployment Steps

1. **Push to GitHub**:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

2. **Deploy on Render**:

   a. Go to [Render Dashboard](https://dashboard.render.com)
   b. Click "New Web Service"
   c. Choose "Build and deploy from a Git repository"
   d. Connect your GitHub repository
   e. Configure the service:

   **Service Settings:**
   - **Name**: vts-training-management
   - **Environment**: Python 3
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn vtstraining.wsgi:application`

   **Environment Variables:**
   - `SECRET_KEY`: Generate a secure secret key
   - `DEBUG`: `False`
   - `ALLOWED_HOSTS`: `your-app-name.onrender.com`
   - `DATABASE_URL`: (Render will provide PostgreSQL URL)

3. **Database Setup**:
   - Render automatically provisions a PostgreSQL database
   - The app will automatically run migrations on deployment

4. **Static Files**:
   - WhiteNoise handles static file serving in production
   - Static files are collected during build process

### Environment Variables

Create these in your Render service settings:

```env
SECRET_KEY=your-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app-name.onrender.com
DATABASE_URL=postgresql://... (auto-provided by Render)
```

### Post-Deployment

1. **Create Admin User**:
   - Access Django admin: `https://your-app-name.onrender.com/admin/`
   - Create a superuser account

2. **Upload Media Files**:
   - Course images and documents will be stored in the filesystem
   - Consider using AWS S3 or similar for production media storage

3. **SSL/HTTPS**:
   - Render automatically provides SSL certificates
   - All connections are secure

## Project Structure

```
VTSTRAINING_CORRECTION-main/
├── myapp/                 # Main application
│   ├── templates/         # HTML templates
│   ├── static/           # CSS, JS, images
│   ├── models.py         # Database models
│   ├── views.py          # View functions
│   └── urls.py           # URL patterns
├── vtstraining/          # Django project settings
├── media/                # User uploaded files
├── staticfiles/          # Collected static files (production)
├── requirements.txt      # Python dependencies
├── Procfile             # Render process definition
├── runtime.txt          # Python version
└── build.sh            # Build script
```

## Features Overview

### Admin Features
- User management (trainees, trainers)
- Course creation and management
- Attendance monitoring
- Certificate generation
- System announcements

### Trainer Features
- Trainee management
- Attendance marking
- Session recording uploads
- Progress tracking
- Announcement creation

### Student Features
- Course enrollment and progress
- Attendance viewing
- Session recordings access
- Certificate downloads
- Personal dashboard

## Support

For issues or questions, please create an issue in the GitHub repository or contact the development team.

## License

This project is proprietary to Vetri Training Solutions.
