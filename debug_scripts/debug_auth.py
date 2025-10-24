import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('c:\\Users\\Admin\\OneDrive\\Desktop\\Vetri-Training-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vtstraining.settings')

# Setup Django
django.setup()

# Check if there are users with trainee profiles
from django.contrib.auth.models import User
from myapp.models import Trainee

print('Total users:', User.objects.count())
print('Users with trainee profiles:')
for user in User.objects.all():
    try:
        trainee = user.trainee
        print(f'  {user.username} - Has trainee profile: {trainee is not None}')
    except:
        print(f'  {user.username} - No trainee profile')

# Check sample attendance data format
from myapp.models import TraineeAttendance
print('\nSample attendance data:')
for att in TraineeAttendance.objects.all()[:2]:
    day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
    print(f'  Expected day_key: {day_key}')
    print(f'  Actual date: {att.date}')
    print(f'  Trainee: {att.trainee.user.username}')
