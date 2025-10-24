import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('c:\\Users\\Admin\\OneDrive\\Desktop\\Vetri-Training-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vtstraining.settings')

# Setup Django
django.setup()

# Check which users have trainee profiles and test login simulation
from django.contrib.auth.models import User
from myapp.models import Trainee

print("=== TESTING USER-TRAINEE RELATIONSHIP ===")

for user in User.objects.all():
    print(f"\nUser: {user.username}")
    print(f"  Email: {user.email}")

    # Check if trainee profile exists in database
    try:
        trainee = Trainee.objects.get(user=user)
        print(f"  ✓ Has trainee profile in DB: {trainee}")
        print(f"  Trainee status: {trainee.status}")
    except Trainee.DoesNotExist:
        print("  ✗ No trainee profile in DB")
    # Test the relationship access
    try:
        trainee_via_relation = user.trainee
        print("  ✗ Not accessible via user.trainee")
    except AttributeError:
        print("  ✗ Not accessible via user.trainee")

    # Check if this user can access attendance data
    if hasattr(user, 'trainee') and user.trainee:
        trainee = user.trainee
        from myapp.models import TraineeAttendance
        from django.utils import timezone
{{ ... }}
            print("  ✓ Should see attendance indicators")
        else:
            print("  ✗ No attendance records this month")
    else:
        print("  ✗ Cannot access attendance data - no trainee profile")

print("\n=== SUMMARY ===")
print("Users that should be able to see attendance data:")
for user in User.objects.all():
    if hasattr(user, 'trainee') and user.trainee:
        print(f"  ✓ {user.username}")
    else:
        print(f"  ✗ {user.username} (no trainee profile)")
