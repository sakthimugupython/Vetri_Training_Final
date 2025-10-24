import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('c:\\Users\\Admin\\OneDrive\\Desktop\\Vetri-Training-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vtstraining.settings')

# Setup Django
django.setup()

# Simulate the attendance_overview view logic for debugging
from django.utils import timezone
from myapp.models import Trainee, TraineeAttendance
from django.contrib.auth.models import User

# Get the current user (assuming it's the one logged in)
# For debugging, let's check all trainees
for user in User.objects.filter(username__in=['sakthi', 'karthik']):
    print(f'\n=== Debugging for user: {user.username} ===')
    trainee = user.trainee
    if not trainee:
        print('No trainee profile found')
        continue

    # Get current month and year
    current_date = timezone.now().date()
    month = current_date.month
    year = current_date.year

    print(f'Current month/year: {month}/{year}')

    # Get attendance data for the current trainee
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start_date = timezone.datetime(year, month, 1).date()
    end_date = timezone.datetime(year, month, last_day).date()

    print(f'Date range: {start_date} to {end_date}')

    # Get attendance records for this trainee
    trainee_attendance = TraineeAttendance.objects.filter(
        trainee=trainee,
        date__range=[start_date, end_date]
    )

    print(f'Attendance records found: {trainee_attendance.count()}')

    # Create attendance data structure for calendar
    attendance_dict = {}
    for att in trainee_attendance:
        day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
        attendance_dict[day_key] = {
            'status': att.status,
            'remarks': att.remarks
        }
        print(f'  Added record: {day_key} -> {att.status}')

    print(f'Total keys in attendance_dict: {len(attendance_dict)}')
    print(f'Sample keys: {list(attendance_dict.keys())[:3]}')

    # Generate calendar data for the month
    import calendar
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    print(f'Calendar weeks: {len(cal)}')
    print(f'Calendar days in first week: {[day for day in cal[0] if day != 0]}')

    # Check if the calendar days match the attendance keys
    for week in cal:
        for day in week:
            if day != 0:
                day_key = f"{year}-{month:02d}-{day:02d}"
                has_attendance = day_key in attendance_dict
                print(f'  Day {day_key}: attendance={"YES" if has_attendance else "NO"}')
