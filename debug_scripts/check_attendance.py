import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('c:\\Users\\Admin\\OneDrive\\Desktop\\Vetri-Training-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vtstraining.settings')

# Setup Django
django.setup()

# Now we can import Django models
from myapp.models import TraineeAttendance, Trainee

print('Total attendance records:', TraineeAttendance.objects.count())
print('Sample attendance records:')
for att in TraineeAttendance.objects.all()[:5]:
    print(f'{att.trainee.user.username} - {att.date} - {att.status}')

print('\nTotal trainees:', Trainee.objects.count())
print('Sample trainees:')
for trainee in Trainee.objects.all()[:3]:
    print(f'{trainee.user.username} - {trainee.user.get_full_name()}')

# Check if there are any attendance records for current month
from datetime import date
current_month = date.today().month
current_year = date.today().year

attendance_this_month = TraineeAttendance.objects.filter(
    date__year=current_year,
    date__month=current_month
)
print(f'\nAttendance records for {current_month}/{current_year}:', attendance_this_month.count())
