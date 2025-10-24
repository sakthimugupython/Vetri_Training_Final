import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('c:\\Users\\Admin\\OneDrive\\Desktop\\Vetri-Training-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vtstraining.settings')

# Setup Django
django.setup()

# Check current user's session and trainee profile
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from myapp.models import Trainee, TraineeAttendance
from django.utils import timezone

print("=== DEBUGGING ATTENDANCE ISSUE ===")

# Check all users and their trainee profiles
print("\n1. USER AND TRAINEE PROFILE CHECK:")
for user in User.objects.all():
    print(f"\nUser: {user.username}")
    print(f"  Is authenticated: {user.is_authenticated}")
    print(f"  Has trainee profile: {hasattr(user, 'trainee')}")

    if hasattr(user, 'trainee'):
        trainee = user.trainee
        print(f"  Trainee: {trainee}")
        print(f"  Trainee status: {trainee.status}")

        # Get attendance for this trainee in current month
        current_date = timezone.now().date()
        month = current_date.month
        year = current_date.year

        from calendar import monthrange
        _, last_day = monthrange(year, month)
        start_date = timezone.datetime(year, month, 1).date()
        end_date = timezone.datetime(year, month, last_day).date()

        trainee_attendance = TraineeAttendance.objects.filter(
            trainee=trainee,
            date__range=[start_date, end_date]
        )

        print(f"  Attendance records for {month}/{year}: {trainee_attendance.count()}")
        for att in trainee_attendance:
            day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
            print(f"    {day_key}: {att.status}")

# Check attendance data format
print("\n2. ATTENDANCE DATA FORMAT CHECK:")
for att in TraineeAttendance.objects.all()[:3]:
    day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
    print(f"  Date: {att.date}")
    print(f"  Day key: {day_key}")
    print(f"  Status: {att.status}")

# Check template context variables that would be passed
print("\n3. TEMPLATE CONTEXT SIMULATION:")
current_date = timezone.now().date()
month = current_date.month
year = current_date.year

from calendar import monthrange
_, last_day = monthrange(year, month)
start_date = timezone.datetime(year, month, 1).date()
end_date = timezone.datetime(year, month, last_day).date()

# Simulate for each trainee
for user in User.objects.filter(username__in=['sakthi', 'karthik']):
    if hasattr(user, 'trainee'):
        trainee = user.trainee
        trainee_attendance = TraineeAttendance.objects.filter(
            trainee=trainee,
            date__range=[start_date, end_date]
        )

        attendance_dict = {}
        for att in trainee_attendance:
            day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
            attendance_dict[day_key] = {
                'status': att.status,
                'remarks': att.remarks
            }

        print(f"\n  For trainee {user.username}:")
        print(f"  Attendance dict: {attendance_dict}")

        # Test template logic
        import calendar
        cal = calendar.monthcalendar(year, month)

        print(f"  Calendar for {month}/{year}:")
        for week in cal:
            for day in week:
                if day != 0:
                    day_key = f"{year}-{month:02d}-{day:02d}"
                    has_attendance = day_key in attendance_dict
                    print(f"    Day {day_key}: attendance_exists={has_attendance}")
                    if has_attendance:
                        print(f"      Status: {attendance_dict[day_key]['status']}")
