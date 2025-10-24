from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import logout, login, authenticate
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.db import models
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.conf import settings
from datetime import timedelta
import os
import re
import json
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    # Fallback for environments where PIL is not available
    Image = ImageDraw = ImageFont = None

from .models import Course, Trainer, Trainee, Certificate, Announcement, DailyAssessment, TraineeAttendance, SessionRecording

# --- HELPER FUNCTIONS ---
def is_admin(user):
    return user.is_authenticated and user.is_superuser

def validate_phone_number(phone):
    """Validate phone number format"""
    # Remove all non-digit characters
    phone_digits = re.sub(r'\D', '', phone)

    # Check if phone number is 10 digits (basic validation)
    if len(phone_digits) != 10:
        return False

    # Check if it starts with valid Indian mobile prefixes (basic check)
    valid_prefixes = ['6', '7', '8', '9']

    # Check if phone number starts with valid prefixes
    if phone_digits[0] not in valid_prefixes:
        return False

    return True

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"

    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"

    return True, "Password is strong"
def generate_certificate_image(certificate_data):
    """
    Generate a certificate image with overlaid text data
    """
    try:
        # Define certificate text positions (adjust these based on your template)
        text_positions = {
            'student_name': (400, 350),      # Center-top area
            'course_name': (400, 420),       # Below student name
            'completion_percentage': (400, 455),  # Marks/Percentage - NEW
            'completion_date': (400, 490),   # Below percentage
            'grade': (400, 560),             # Below date
            'certificate_id': (650, 650),    # Bottom right
        }

        # Font settings - Use default fonts for better compatibility
        try:
            # Try to use DejaVu fonts if available (Linux/Mac)
            title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
            regular_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
            small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
        except (OSError, IOError):
            try:
                # Try Windows fonts
                title_font = ImageFont.truetype('arial.ttf', 36)
                regular_font = ImageFont.truetype('arial.ttf', 24)
                small_font = ImageFont.truetype('arial.ttf', 18)
            except (OSError, IOError):
                # Fallback to default font
                title_font = ImageFont.load_default()
                regular_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

        # Template image path
        template_path = os.path.join(settings.MEDIA_ROOT, 'certificate_templates', 'certificate_template.png')

        # Check if template exists, if not create a simple colored background
        if os.path.exists(template_path):
            # Open the certificate template
            certificate_img = Image.open(template_path)
        else:
            # Create a simple certificate background (fallback)
            certificate_img = Image.new('RGB', (800, 600), color='#f8f9fa')
            # Add a border
            draw = ImageDraw.Draw(certificate_img)
            draw.rectangle([50, 50, 750, 550], outline='#2d3748', width=3)

        # Get image dimensions
        img_width, img_height = certificate_img.size
        draw = ImageDraw.Draw(certificate_img)

        # Overlay text data
        # Student name (centered, large font)
        student_name = certificate_data.get('student_name', 'Student Name')
        draw.text(text_positions['student_name'], student_name, fill='#000000', font=title_font, anchor='mm')

        # Course name
        course_name = certificate_data.get('course_name', 'Course Name')
        draw.text(text_positions['course_name'], f"Course: {course_name}", fill='#000000', font=regular_font, anchor='mm')

        # Completion percentage (marks)
        completion_percentage = certificate_data.get('completion_percentage', 0)
        draw.text(text_positions['completion_percentage'], f"Marks: {completion_percentage}%", fill='#000000', font=regular_font, anchor='mm')

        # Completion date
        completion_date = certificate_data.get('completion_date', 'Date')
        draw.text(text_positions['completion_date'], f"Completed on: {completion_date}", fill='#000000', font=regular_font, anchor='mm')

        # Grade
        grade = certificate_data.get('grade', 'A')
        draw.text(text_positions['grade'], f"Grade: {grade}", fill='#000000', font=regular_font, anchor='mm')

        # Certificate ID (smaller font, bottom right)
        certificate_id = certificate_data.get('certificate_id', 'CERT-001')
        draw.text(text_positions['certificate_id'], f"ID: {certificate_id}", fill='#000000', font=small_font, anchor='mm')

        # Add debug information (remove this in production)
        print(f"Certificate generated for: {student_name}")
        print(f"Course: {course_name}, Marks: {completion_percentage}%, Grade: {grade}")
        print(f"Certificate ID: {certificate_id}")
        print(f"Template path: {template_path}")
        print(f"Template exists: {os.path.exists(template_path)}")

        # Save the generated certificate
        output_dir = os.path.join(settings.MEDIA_ROOT, 'certificates')
        os.makedirs(output_dir, exist_ok=True)

        output_filename = f"certificate_{certificate_id}.png"
        output_path = os.path.join(output_dir, output_filename)

        certificate_img.save(output_path, 'PNG', quality=95)

        return output_path

    except Exception as e:
        print(f"Error generating certificate: {str(e)}")
        return None

# --- TRAINEE ATTENDANCE VIEWS ---
from django.db.models import Count

@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def trainee_attendance_list(request):
	trainees = Trainee.objects.select_related('user', 'course').all()
	attendance_data = []
	for trainee in trainees:
		present_days = trainee.attendances.filter(status='present').count()
		absent_days = trainee.attendances.filter(status='absent').count()
		total_days = trainee.attendances.count()
		attendance_data.append({
			'trainee': trainee,
			'present_days': present_days,
			'absent_days': absent_days,
			'total_days': total_days,
		})
	return render(request, 'myapp/trainee_attendance_list.html', {'attendance_data': attendance_data})

@login_required(login_url='/trainer-login/')
def update_trainee_attendance(request, trainee_id):
	trainee = get_object_or_404(Trainee, id=trainee_id)
	trainer = getattr(request.user, 'trainer', None)
	if not trainer:
		return redirect('trainer_login')
	today = timezone.now().date()
	attendance, created = TraineeAttendance.objects.get_or_create(trainee=trainee, date=today)
	if request.method == 'POST':
		status = request.POST.get('status')
		remarks = request.POST.get('remarks', '')
		attendance.status = status
		attendance.remarks = remarks
		attendance.save()
		messages.success(request, 'Attendance updated!')
		return redirect('trainer_trainee_attendance')
	return render(request, 'myapp/update_trainee_attendance.html', {'trainee': trainee, 'attendance': attendance})

@login_required(login_url='/trainer-login/')

def trainee_attendance_trainer(request):
	trainer = getattr(request.user, 'trainer', None)
	if not trainer:
		return redirect('trainer_login')
	trainees = Trainee.objects.filter(trainer=trainer).select_related('user', 'course')
	# Group trainees by batch
	batch_numbers = [int(t.batch) for t in trainees if t.batch and t.batch.isdigit()]
	if batch_numbers:
		min_batch = min(batch_numbers)
		max_batch = max(batch_numbers)
		all_batches = [str(i) for i in range(min_batch, max_batch + 1)]
	else:
		all_batches = ['No Batch']
	batch_dict = {batch: [] for batch in all_batches}
	for trainee in trainees:
		batch = trainee.batch or 'No Batch'
		batch_dict.setdefault(batch, []).append(trainee)

	today = timezone.now().date()
	status_choices = [
		('present', 'Present'),
		('absent', 'Absent'),
		('informed', 'Informed'),
		('not_informed', 'Not Informed'),
	]

	if request.method == 'POST':
		for trainee in trainees:
			status = request.POST.get(f'status_{trainee.id}')
			if status:
				attendance, _ = TraineeAttendance.objects.get_or_create(trainee=trainee, date=today)

				# Handle absent with sub-type (informed/not_informed)
				if status == 'absent':
					absent_type = request.POST.get(f'absent_type_{trainee.id}')
					if absent_type in ['informed', 'not_informed']:
						attendance.status = absent_type
						remarks = request.POST.get(f'remarks_{trainee.id}', '')
						attendance.remarks = remarks
					else:
						attendance.status = 'absent'
				else:
					attendance.status = status

				attendance.save()
		messages.success(request, 'Attendance updated for all selected trainees!')
		return redirect('trainer_trainee_attendance')

	# For each trainee, get today's status if exists
	trainee_status = {}
	trainee_remarks = {}
	for trainee in trainees:
		att = TraineeAttendance.objects.filter(trainee=trainee, date=today).first()
		if att:
			trainee_status[trainee.id] = att.status
			trainee_remarks[trainee.id] = att.remarks
		else:
			trainee_status[trainee.id] = ''
			trainee_remarks[trainee.id] = ''

	return render(request, 'myapp/trainee_attendance_trainer.html', {
		'batch_dict': batch_dict,
		'status_choices': status_choices,
		'trainee_status': trainee_status,
		'trainee_remarks': trainee_remarks,
    })


@login_required(login_url='/student-login/')
def trainee_attendance_overview(request):
    trainee = getattr(request.user, 'trainee', None)
    if not trainee:
        return redirect('student_login')

    # Get current month and year from request or default to current
    current_date = timezone.now().date()
    month = int(request.GET.get('month', current_date.month))
    year = int(request.GET.get('year', current_date.year))

    # Handle month/year navigation
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1

    # Get attendance data for the current trainee
    from calendar import monthrange, month_name
    _, last_day = monthrange(year, month)
    start_date = timezone.datetime(year, month, 1).date()
    end_date = timezone.datetime(year, month, last_day).date()

    # Get attendance records for this trainee
    trainee_attendance = TraineeAttendance.objects.filter(
        trainee=trainee,
        date__range=[start_date, end_date]
    )

    # Create attendance data structure for calendar
    attendance_dict = {}
    for att in trainee_attendance:
        day_key = f"{att.date.year}-{att.date.month:02d}-{att.date.day:02d}"
        attendance_dict[day_key] = {
            'status': att.status,
            'remarks': att.remarks
        }

    # Calculate attendance statistics
    # Calculate total days in the month
    _, total_days = monthrange(year, month)

    # Count different attendance statuses
    present_count = sum(1 for att in attendance_dict.values() if att['status'] == 'present')
    absent_count = sum(1 for att in attendance_dict.values() if att['status'] == 'absent')
    informed_count = sum(1 for att in attendance_dict.values() if att['status'] == 'informed')
    not_informed_count = sum(1 for att in attendance_dict.values() if att['status'] == 'not_informed')

    # Calculate percentages
    total_records = present_count + absent_count + informed_count + not_informed_count
    present_percentage = (present_count / total_records * 100) if total_records > 0 else 0
    absent_percentage = (absent_count / total_records * 100) if total_records > 0 else 0
    informed_percentage = (informed_count / total_records * 100) if total_records > 0 else 0
    not_informed_percentage = (not_informed_count / total_records * 100) if total_records > 0 else 0

    context = {
        'trainee': trainee,
        'attendance_dict': attendance_dict,
        'month_name': month_name[month],
        'year': year,
        'month': month,
        'current_date': current_date,
        'statistics': {
            'total_days': total_days,
            'present_count': present_count,
            'absent_count': absent_count,
            'informed_count': informed_count,
            'not_informed_count': not_informed_count,
            'present_percentage': round(present_percentage, 1),
            'absent_percentage': round(absent_percentage, 1),
            'informed_percentage': round(informed_percentage, 1),
            'not_informed_percentage': round(not_informed_percentage, 1),
        }
    }

    return render(request, 'myapp/attendance_overview.html', context)


# --- EDIT ANNOUNCEMENT VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
@csrf_protect
def edit_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        content = request.POST.get('content')
        target_audience = request.POST.get('target_audience')
        post_date = request.POST.get('post_date')
        
        announcement.title = title
        announcement.content = content
        announcement.short_description = description
        announcement.target_audience = target_audience
        announcement.date_posted = post_date if post_date else None
        announcement.save()
        
        messages.success(request, 'Announcement updated successfully!')
        return redirect('announcements')
    return render(request, 'myapp/edit_announcement.html', {'announcement': announcement})

# --- ADD ANNOUNCEMENT VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
@csrf_protect
def add_announcement(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        content = request.POST.get('content')
        target_audience = request.POST.get('target_audience')
        post_date = request.POST.get('post_date')
        
        Announcement.objects.create(
            title=title,
            content=content,
            short_description=description,
            target_audience=target_audience,
            date_posted=post_date if post_date else None,
            posted_by='Admin',
            academy='Vetri Academy'
        )
        messages.success(request, 'Announcement added successfully!')
        return redirect('announcements')
    return render(request, 'myapp/add_announcement.html')

# --- DELETE ANNOUNCEMENT ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def delete_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully!')
        return redirect('announcements')
    return render(request, 'myapp/confirm_delete.html', {'object': announcement, 'type': 'Announcement'})
# --- ANNOUNCEMENTS VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def announcements(request):
	# Clear any existing messages when accessing the announcements page
	from django.contrib.messages import get_messages
	list(get_messages(request))  # This clears the messages

	# Check user type and show appropriate announcements
	user = request.user
	announcements = []

	if user.is_superuser:
		# Admin sees all announcements
		announcements = Announcement.objects.order_by('-date_posted', '-id')
		can_create = True
		user_type = 'admin'
	elif hasattr(user, 'trainer'):
		# Trainers see announcements targeted to 'all' and 'trainers'
		announcements = Announcement.objects.filter(
			models.Q(target_audience='all') | models.Q(target_audience='trainers')
		).order_by('-date_posted', '-id')
		can_create = True
		user_type = 'trainer'
	else:
		# Trainees see announcements targeted to 'all' and 'trainees'
		announcements = Announcement.objects.filter(
			models.Q(target_audience='all') | models.Q(target_audience='trainees')
		).order_by('-date_posted', '-id')
		can_create = False
		user_type = 'trainee'

	return render(request, 'myapp/announcements.html', {
		'announcements': announcements,
		'can_create': can_create,
		'user_type': user_type
	})

@login_required(login_url='/trainer-login/')
def create_announcement(request):
	trainer = getattr(request.user, 'trainer', None)
	if not trainer:
		return redirect('trainer_login')

	# Clear any existing messages to prevent showing old messages
	from django.contrib.messages import get_messages
	list(get_messages(request))  # This clears the messages

	if request.method == 'POST':
		title = request.POST.get('title')
		description = request.POST.get('description')
		content = request.POST.get('content')
		target_audience = request.POST.get('target_audience', 'all')

		if title and content:
			Announcement.objects.create(
				title=title,
				content=content,
				short_description=description,
				target_audience=target_audience,
				date_posted=timezone.now().date(),
				posted_by=f"Trainer {trainer.user.get_full_name()}",
				academy='Vetri Academy'
			)
			messages.success(request, 'Announcement posted successfully!')
			return redirect('trainer_announcements')
		else:
			messages.error(request, 'Please fill in all required fields.')

	return render(request, 'myapp/create_announcement.html')


@login_required(login_url='/trainer-login/')
def trainer_announcements(request):
	trainer = getattr(request.user, 'trainer', None)
	if not trainer:
		return redirect('trainer_login')

	# Clear any existing messages when accessing the announcements page
	from django.contrib.messages import get_messages
	list(get_messages(request))  # This clears the messages

	# Handle mark as read request
	if request.method == 'POST' and request.POST.get('mark_as_read') == 'true':
		# Get ALL announcements for trainers and mark them as viewed
		all_trainer_announcements = Announcement.objects.filter(
			models.Q(target_audience='all') | models.Q(target_audience='trainers')
		).order_by('-date_posted', '-id')

		announcement_ids = [ann.id for ann in all_trainer_announcements]
		viewed_announcements = request.session.get('viewed_announcements', [])
		request.session['viewed_announcements'] = list(set(viewed_announcements + announcement_ids))
		request.session.modified = True

		# Return JSON response for AJAX
		return JsonResponse({'success': True, 'marked_count': len(announcement_ids)})

	# Get ALL announcements for trainers and mark them as viewed
	all_trainer_announcements = Announcement.objects.filter(
		models.Q(target_audience='all') | models.Q(target_audience='trainers')
	).order_by('-date_posted', '-id')

	# Mark ALL announcements as viewed in session (not just recent 10)
	announcement_ids = [ann.id for ann in all_trainer_announcements]
	viewed_announcements = request.session.get('viewed_announcements', [])
	request.session['viewed_announcements'] = list(set(viewed_announcements + announcement_ids))
	request.session.modified = True

	# Get recent announcements for display (last 10 for the list)
	recent_announcements = all_trainer_announcements[:10]

	# Show existing announcements for trainers
	announcements = Announcement.objects.filter(
		models.Q(target_audience='all') | models.Q(target_audience='trainers')
	).order_by('-date_posted', '-id')

	return render(request, 'myapp/trainer_announcements.html', {
		'announcements': announcements
	})

@login_required(login_url='/student-login/')
def trainee_announcements(request):
	trainee = getattr(request.user, 'trainee', None)
	if not trainee:
		return redirect('student_login')

	# Clear any existing messages when accessing the announcements page
	from django.contrib.messages import get_messages
	list(get_messages(request))  # This clears the messages

	# Handle mark as read request
	if request.method == 'POST' and request.POST.get('mark_as_read') == 'true':
		# Get ALL announcements for trainees and mark them as viewed
		all_trainee_announcements = Announcement.objects.filter(
			models.Q(target_audience='all') | models.Q(target_audience='trainees')
		).order_by('-date_posted', '-id')

		announcement_ids = [ann.id for ann in all_trainee_announcements]
		viewed_announcements = request.session.get('viewed_announcements', [])
		request.session['viewed_announcements'] = list(set(viewed_announcements + announcement_ids))
		request.session.modified = True

		# Return JSON response for AJAX
		return JsonResponse({'success': True, 'marked_count': len(announcement_ids)})

	# Get ALL announcements for trainees and mark them as viewed
	all_trainee_announcements = Announcement.objects.filter(
		models.Q(target_audience='all') | models.Q(target_audience='trainees')
	).order_by('-date_posted', '-id')

	# Mark ALL announcements as viewed in session (not just recent 10)
	announcement_ids = [ann.id for ann in all_trainee_announcements]
	viewed_announcements = request.session.get('viewed_announcements', [])
	request.session['viewed_announcements'] = list(set(viewed_announcements + announcement_ids))
	request.session.modified = True

	# Get recent announcements for display (last 10 for the list)
	recent_announcements = all_trainee_announcements[:10]

	# Show existing announcements for trainees (read-only)
	announcements = Announcement.objects.filter(
		models.Q(target_audience='all') | models.Q(target_audience='trainees')
	).order_by('-date_posted', '-id')

	return render(request, 'myapp/trainee_announcements.html', {
		'announcements': announcements,
		'can_create': False,  # Trainees cannot create announcements
		'trainee': trainee,  # Add trainee object to context
	})




# --- EDIT TRAINEE VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def edit_trainee(request, trainee_id):
	trainee = get_object_or_404(Trainee, id=trainee_id)
	courses = Course.objects.all()
	trainers = Trainer.objects.select_related('user').all()
	if request.method == 'POST':
		name = request.POST.get('name')
		email = request.POST.get('email')
		phone = request.POST.get('phone')
		course_id = request.POST.get('course')
		trainer_id = request.POST.get('trainer')
		batch = request.POST.get('batch')
		progress = request.POST.get('progress')
		certificate_status = request.POST.get('certificate_status')
		status = request.POST.get('status')
		# Update user fields
		trainee.user.first_name = name
		trainee.user.email = email
		trainee.user.save()
		# Update trainee fields
		trainee.phone = phone
		trainee.batch = batch
		trainee.progress = progress
		trainee.certificate_status = certificate_status
		trainee.status = status
		# Update course and trainer
		trainee.course = Course.objects.get(id=course_id) if course_id else None
		trainee.trainer = Trainer.objects.get(id=trainer_id) if trainer_id else None
		trainee.save()
		messages.success(request, 'Trainee updated successfully!')
		return redirect('trainee_list')
	return render(request, 'myapp/edit_trainee.html', {
		'trainee': trainee,
		'courses': courses,
		'trainers': trainers,
	})




# --- TRAINEE LIST VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def trainee_list(request):
	sort = request.GET.get('sort')
	search_query = request.GET.get('search', '').strip()
	batch_filter = request.GET.get('batch_filter', '').strip()

	# Base queryset - get trainees with related user data
	trainees = Trainee.objects.select_related('user', 'course').filter(user__is_superuser=False)

	# Apply search filter if query exists
	if search_query:
		trainees = trainees.filter(
			models.Q(user__first_name__icontains=search_query) |
			models.Q(user__last_name__icontains=search_query) |
			models.Q(user__username__icontains=search_query) |
			models.Q(user__email__icontains=search_query) |
			models.Q(course__name__icontains=search_query) |
			models.Q(batch__icontains=search_query) |
			models.Q(trainee_code__icontains=search_query)
		)

	# Apply batch filter if provided
	if batch_filter:
		trainees = trainees.filter(batch__icontains=batch_filter)

	# Apply sorting
	if sort == 'course':
		trainees = trainees.order_by('course__name')
	elif sort == 'batch':
		trainees = trainees.order_by('batch')

	total_trainees = trainees.count()
	active_trainees = trainees.filter(status='Active').count() if hasattr(Trainee, 'status') else 0
	on_hold_trainees = trainees.filter(status='On Hold').count() if hasattr(Trainee, 'status') else 0
	completed_trainees = trainees.filter(status='Completed').count() if hasattr(Trainee, 'status') else 0

	return render(request, 'myapp/trainee_list.html', {
		'trainees': trainees,
		'total_trainees': total_trainees,
		'active_trainees': active_trainees,
		'on_hold_trainees': on_hold_trainees,
		'completed_trainees': completed_trainees,
		'search_query': search_query,
		'batch_filter': batch_filter,
	})

# --- ADD TRAINEE VIEW (placeholder) ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def add_trainee(request):
	courses = Course.objects.all()
	trainers = Trainer.objects.select_related('user').all()
	# Prepare trainer data for JS: id, name, batches
	import json
	trainer_data = [
		{
			'id': trainer.id,
			'name': trainer.user.get_full_name() or trainer.user.username,
			'batches': trainer.batches if hasattr(trainer, 'batches') else 1
		}
		for trainer in trainers
	]
	trainer_data_json = json.dumps(trainer_data)
	show_success = False

	if request.method == 'POST':
		# Auto-generate trainee_code
		next_id = Trainee.objects.count() + 1
		trainee_code = f"{next_id:03d}"

		# Get form data
		name = request.POST.get('name', '').strip()
		email = request.POST.get('email', '').strip()
		phone = request.POST.get('phone', '').strip()
		password = request.POST.get('password', '')
		course_id = request.POST.get('course', '').strip()
		status = request.POST.get('status', '').strip()
		batch = request.POST.get('batch', '').strip()
		progress = request.POST.get('progress', '').strip()
		trainer_id = request.POST.get('trainer', '').strip()
		profile_image = request.FILES.get('profile_image')

		# Validation errors dictionary
		errors = {}

		# Name validation
		if not name:
			errors['name'] = 'Name is required.'
		elif len(name) < 2:
			errors['name'] = 'Name must be at least 2 characters long.'
		elif len(name) > 100:
			errors['name'] = 'Name must be less than 100 characters.'
		elif not re.match(r"^[a-zA-Z\s']+$", name):
			errors['name'] = 'Name can only contain letters, spaces, and apostrophes.'

		# Email validation
		if not email:
			errors['email'] = 'Email is required.'
		else:
			try:
				validate_email(email)
				# Check for duplicate email
				if User.objects.filter(email=email).exists():
					errors['email'] = 'A user with this email already exists.'
			except ValidationError:
				errors['email'] = 'Please enter a valid email address.'

		# Phone validation
		if not phone:
			errors['phone'] = 'Phone number is required.'
		elif not validate_phone_number(phone):
			errors['phone'] = 'Please enter a valid 10-digit phone number (numbers only).'

		# Password validation
		is_valid_password, password_error = validate_password_strength(password)
		if not password:
			errors['password'] = 'Password is required.'
		elif not is_valid_password:
			errors['password'] = password_error

		# Course validation
		if not course_id:
			errors['course'] = 'Course selection is required.'
		else:
			try:
				course = Course.objects.get(id=course_id, is_active=True)
			except Course.DoesNotExist:
				errors['course'] = 'Selected course is not available.'

		# Trainer validation
		if not trainer_id:
			errors['trainer'] = 'Trainer selection is required.'
		else:
			try:
				trainer_obj = Trainer.objects.get(id=trainer_id)
			except Trainer.DoesNotExist:
				errors['trainer'] = 'Selected trainer does not exist.'

		# Batch validation
		if not batch:
			errors['batch'] = 'Batch selection is required.'
		elif batch and trainer_id:
			try:
				trainer_obj = Trainer.objects.get(id=trainer_id)
				max_batches = trainer_obj.batches or 1
				try:
					batch_num = int(batch)
					if batch_num < 1 or batch_num > max_batches:
						errors['batch'] = f'Batch must be between 1 and {max_batches}.'
				except ValueError:
					errors['batch'] = 'Batch must be a valid number.'
			except Trainer.DoesNotExist:
				errors['trainer'] = 'Selected trainer does not exist.'

		# Progress validation
		if not progress:
			errors['progress'] = 'Progress percentage is required.'
		else:
			try:
				progress_num = float(progress)
				if progress_num < 0 or progress_num > 100:
					errors['progress'] = 'Progress must be between 0 and 100.'
			except ValueError:
				errors['progress'] = 'Progress must be a valid number.'

		# Status validation
		valid_statuses = ['Active', 'On Hold', 'Completed']
		if not status:
			errors['status'] = 'Status selection is required.'
		elif status not in valid_statuses:
			errors['status'] = 'Please select a valid status.'

		# If there are validation errors, return to form with errors
		if errors:
			return render(request, 'myapp/add_trainee.html', {
				'courses': courses,
				'trainers': trainers,
				'trainer_data_json': trainer_data_json,
				'errors': errors,
				'form_data': {
					'name': name,
					'email': email,
					'phone': phone,
					'course': course_id,
					'status': status,
					'batch': batch,
					'progress': progress,
					'trainer': trainer_id,
				}
			})

		# Create user for trainee
		base_username = email.split('@')[0] if email else trainee_code
		username = base_username
		# Ensure username is unique
		counter = 1
		while User.objects.filter(username=username).exists():
			username = f"{base_username}_{counter}"
			counter += 1

		user = User.objects.create_user(username=username, email=email, first_name=name)
		user.set_password(password)
		user.save()

		# Get course and trainer
		course = Course.objects.get(id=course_id) if course_id else None
		trainer = Trainer.objects.get(id=trainer_id) if trainer_id else None

		# Create trainee
		trainee = Trainee.objects.create(
			user=user,
			course=course,
			phone=phone,
		)
		# Save extra fields (batch, progress, status, profile_image, trainer)
		trainee.batch = batch
		trainee.progress = float(progress)
		trainee.status = status
		if profile_image:
			trainee.profile_image = profile_image
		if trainer:
			trainee.trainer = trainer
		trainee.trainee_code = trainee_code
		trainee.save()

		# Increment only the assigned trainer's batches/count if needed
		if trainer:
			trainer.batches = (trainer.batches or 0) + 1
			trainer.save()

		# No need to increment course count, as course.trainees.count() is dynamic

		request.session['show_trainee_success'] = True
		return redirect('add_trainee')

	show_success = request.session.pop('show_trainee_success', False)
	return render(request, 'myapp/add_trainee.html', {
		'courses': courses,
		'trainers': trainers,
		'trainer_data_json': trainer_data_json,
		'show_success': show_success
	})




# --- DELETE COURSE ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def delete_course(request, course_id):
	course = get_object_or_404(Course, id=course_id)
	if request.method == 'POST':
		course.delete()
		messages.success(request, 'Course deleted successfully!')
		return redirect('course_list')
	return render(request, 'myapp/confirm_delete.html', {'object': course, 'type': 'Course'})

# --- DELETE TRAINER ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def delete_trainer(request, trainer_id):
	trainer = get_object_or_404(Trainer, id=trainer_id)
	if request.method == 'POST':
		user = trainer.user
		trainer.delete()
		user.delete()
		messages.success(request, 'Trainer deleted successfully!')
		return redirect('trainer_list')
	return render(request, 'myapp/confirm_delete.html', {'object': trainer, 'type': 'Trainer'})

# Trainer dashboard view
@login_required(login_url='/trainer-login/')
def trainer_dashboard(request):
    user = request.user
    trainer = getattr(user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    # Allow trainer to toggle their own status unless admin_locked
    if request.method == 'POST':
        print('POST data:', request.POST)
        print('admin_locked:', trainer.admin_locked)
        if request.POST.get('toggle_status') == 'toggle' and not trainer.admin_locked:
            print('Toggling status. Current:', trainer.status)
            if trainer.status == 'Active':
                trainer.status = 'Inactive'
            else:
                trainer.status = 'Active'
            trainer.save()
            print('New status:', trainer.status)
            messages.success(request, f"Your status has been set to {trainer.status}.")
            return redirect('trainer_dashboard')

    # Get all courses assigned to trainer (courses where this trainer is assigned)
    assigned_courses = Course.objects.filter(trainer=trainer, is_active=True)
    assigned_courses_count = assigned_courses.count()
    
    # Get all trainees under the assigned courses
    all_trainees = []
    course_stats = []
    total_trainees = 0
    
    for course in assigned_courses:
        trainees = course.trainees.select_related('user').filter(user__is_superuser=False).all()
        course_trainees_count = trainees.count()
        total_trainees += course_trainees_count
        course_stats.append({
            'name': course.name,
            'code': course.code,
            'mode': course.mode,
            'trainees_count': course_trainees_count,
            'category': course.category
        })
        for trainee in trainees:
            # Calculate progress from assessments
            total_assessments = trainee.assessments.count()
            completed_assessments = trainee.assessments.filter(is_completed=True).count()
            progress = int((completed_assessments / total_assessments) * 100) if total_assessments > 0 else 0
            has_pending = total_assessments > completed_assessments

            # Get today's attendance
            today = timezone.now().date()
            today_attendance = TraineeAttendance.objects.filter(trainee=trainee, date=today).first()
            attendance_today = today_attendance.status if today_attendance else 'not_marked'

            all_trainees.append({
                'name': trainee.user.get_full_name() or trainee.user.username,
                'course': course.name,
                'progress': progress,
                'status': trainee.status,
                'batch': trainee.batch,
                'has_pending': has_pending,
                'attendance_today': attendance_today
            })
    
    # Sort trainees by status but don't limit - show all trainees
    all_trainees = sorted(all_trainees, key=lambda x: (x['status'] != 'Active', x['progress']), reverse=True)
    
    # Get recent announcements for trainers (last 3 for display)
    recent_announcements = Announcement.objects.filter(
        models.Q(target_audience='all') | models.Q(target_audience='trainers')
    ).order_by('-date_posted', '-id')[:3]

    # Get ALL announcements for trainers to calculate real unread count
    all_trainer_announcements = Announcement.objects.filter(
        models.Q(target_audience='all') | models.Q(target_audience='trainers')
    ).order_by('-date_posted', '-id')

    # Get unread announcement count (based on session tracking)
    viewed_announcements = request.session.get('viewed_announcements', [])
    unread_announcements_count = len([ann for ann in all_trainer_announcements if ann.id not in viewed_announcements])
    
    # Prepare course data for chart
    import json
    course_labels = [course['name'] for course in course_stats]
    course_counts = [course['trainees_count'] for course in course_stats]
    
    # Convert to JSON strings
    course_labels_json = json.dumps(course_labels)
    course_counts_json = json.dumps(course_counts)
    
    return render(request, 'trainer/dashboard.html', {
        'user': user,
        'trainer': trainer,
        'courses': assigned_courses,
        'course_stats': course_stats,
        'assigned_courses_count': assigned_courses_count,
        'total_trainees': total_trainees,
        'recent_trainees': all_trainees,  # Changed from recent_trainees to all_trainees
        'course_labels': course_labels_json,
        'course_counts': course_counts_json,
        'recent_announcements': recent_announcements,
        'unread_announcements_count': unread_announcements_count,
        'all_announcements': all_trainer_announcements,  # Add this for template access
    })

@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def edit_course(request, course_id):
	course = get_object_or_404(Course, id=course_id)
	trainers = Trainer.objects.select_related('user').all()
	if request.method == 'POST':
		course.name = request.POST.get('name')
		course.code = request.POST.get('code')
		trainer_id = request.POST.get('trainer')
		course.trainer = Trainer.objects.get(id=trainer_id) if trainer_id else None
		course.duration = request.POST.get('duration')
		course.mode = request.POST.get('mode')
		course.category = request.POST.get('category')
		course.description = request.POST.get('description')
		course.learning_outcomes = request.POST.get('learning_outcomes')
		cover_image = request.FILES.get('cover_image')
		syllabus = request.FILES.get('syllabus')
		if cover_image:
			course.cover_image = cover_image
		if syllabus:
			course.syllabus = syllabus
		course.save()
		messages.success(request, f'Course "{course.name}" updated successfully!')
		return redirect('course_list')
	return render(request, 'myapp/edit_course.html', {'course': course, 'trainers': trainers})



# --- EDIT TRAINER VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def edit_trainer(request, trainer_id):
	trainer = get_object_or_404(Trainer, id=trainer_id)
	if request.method == 'POST':
		full_name = request.POST.get('full_name')
		email = request.POST.get('email')
		phone = request.POST.get('phone')
		expertise = request.POST.get('expertise')
		assign_courses = request.POST.get('assign_courses')
		bio = request.POST.get('bio')
		trainer_code = request.POST.get('trainer_code')
		batches = request.POST.get('batches') or 0
		status = request.POST.get('status') or 'Active'
		profile_image = request.FILES.get('profile_image')

		# Validation errors dictionary
		errors = {}

		# Full name validation - only letters, spaces, and apostrophes allowed
		if not full_name:
			errors['full_name'] = 'Full name is required.'
		else:
			import re
			name_pattern = r"^[a-zA-Z\s']+$"
			if not re.match(name_pattern, full_name):
				errors['full_name'] = 'Full name can only contain letters, spaces, and apostrophes.'
			elif len(full_name) < 2:
				errors['full_name'] = 'Full name must be at least 2 characters long.'
			elif len(full_name) > 100:
				errors['full_name'] = 'Full name must be less than 100 characters.'

		# Email validation
		if not email:
			errors['email'] = 'Email is required.'
		else:
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, email):
				errors['email'] = 'Please enter a valid email address.'
			elif User.objects.filter(email=email).exclude(id=trainer.user.id).exists():
				errors['email'] = 'A user with this email already exists.'

		# Phone validation (if provided)
		if phone:
			phone_pattern = r'^[0-9]{10}$'
			if not re.match(phone_pattern, phone):
				errors['phone'] = 'Please enter a valid 10-digit phone number (numbers only, no spaces or special characters).'
			elif len(phone) != 10:
				errors['phone'] = 'Phone number must be exactly 10 digits.'

		# Expertise validation (if provided) - only letters and spaces allowed
		if expertise:
			expertise_pattern = r"^[a-zA-Z\s]+$"
			if not re.match(expertise_pattern, expertise):
				errors['expertise'] = 'Area of expertise can only contain letters and spaces.'
			elif len(expertise) > 255:
				errors['expertise'] = 'Area of expertise must be less than 255 characters.'

		# Assign courses validation (if provided) - only letters and spaces allowed
		if assign_courses:
			courses_pattern = r"^[a-zA-Z\s]+$"
			if not re.match(courses_pattern, assign_courses):
				errors['assign_courses'] = 'Assigned courses can only contain letters and spaces.'
			elif len(assign_courses) > 255:
				errors['assign_courses'] = 'Assigned courses must be less than 255 characters.'

		# Bio validation (if provided)
		if bio and len(bio) > 1000:
			errors['bio'] = 'Bio must be less than 1000 characters.'

		# Trainer code validation (if provided)
		if trainer_code:
			if len(trainer_code) > 50:
				errors['trainer_code'] = 'Trainer code must be less than 50 characters.'
			elif Trainer.objects.filter(trainer_code=trainer_code).exclude(id=trainer_id).exists():
				errors['trainer_code'] = 'This trainer code is already in use.'

		# Batches validation
		try:
			batches_num = int(batches)
			if batches_num < 0:
				errors['batches'] = 'Number of batches cannot be negative.'
			elif batches_num > 100:
				errors['batches'] = 'Number of batches cannot exceed 100.'
		except ValueError:
			errors['batches'] = 'Number of batches must be a valid number.'

		# If there are validation errors, return to form with errors
		if errors:
			return render(request, 'myapp/edit_trainer.html', {
				'trainer': trainer,
				'errors': errors
			})

		# Update trainer fields
		trainer.user.first_name = full_name
		trainer.user.email = email
		trainer.user.save()
		trainer.phone = phone
		trainer.expertise = expertise
		trainer.assign_courses = assign_courses
		trainer.bio = bio
		trainer.trainer_code = trainer_code
		trainer.batches = batches
		trainer.status = status
		if profile_image:
			trainer.profile_image = profile_image
		trainer.save()
		messages.success(request, f'Trainer "{full_name}" updated successfully!')
		return redirect('trainer_list')
	return render(request, 'myapp/edit_trainer.html', {'trainer': trainer})


# --- HELPER FUNCTIONS ---
def is_admin(user):
	return user.is_authenticated and user.is_superuser

@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def add_trainer(request):
	if request.method == 'POST':
		# Auto-generate trainer_code
		next_id = Trainer.objects.count() + 1
		trainer_code = f"{next_id:03d}"

		# Get form data
		full_name = request.POST.get('full_name', '').strip()
		email = request.POST.get('email', '').strip()
		phone = request.POST.get('phone', '').strip()
		expertise = request.POST.get('expertise', '').strip()
		assign_courses = request.POST.get('assign_courses', '').strip()
		bio = request.POST.get('bio', '').strip()
		username = request.POST.get('username', '').strip()
		password = request.POST.get('password', '')
		password_confirm = request.POST.get('password_confirm', '')
		batches = request.POST.get('batches', '0').strip()
		trainer_code_manual = request.POST.get('trainer_code', '').strip()
		profile_image = request.FILES.get('profile_image')

		# Validation errors dictionary
		errors = {}

		# Validate required fields
		if not full_name:
			errors['full_name'] = 'Full name is required.'
		else:
			import re
			# Full name validation - only letters, spaces, and apostrophes allowed
			name_pattern = r"^[a-zA-Z\s']+$"
			if not re.match(name_pattern, full_name):
				errors['full_name'] = 'Full name can only contain letters, spaces, and apostrophes.'
			elif len(full_name) < 2:
				errors['full_name'] = 'Full name must be at least 2 characters long.'
			elif len(full_name) > 100:
				errors['full_name'] = 'Full name must be less than 100 characters.'

		if not email:
			errors['email'] = 'Email is required.'
		else:
			# Email format validation
			import re
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, email):
				errors['email'] = 'Please enter a valid email address.'
			elif User.objects.filter(email=email).exists():
				errors['email'] = 'A user with this email already exists.'

		# Username validation
		if not username:
			errors['username'] = 'Username is required.'
		elif len(username) < 3:
			errors['username'] = 'Username must be at least 3 characters long.'
		elif len(username) > 50:
			errors['username'] = 'Username must be less than 50 characters.'
		elif not username.isalnum():
			errors['username'] = 'Username can only contain letters and numbers.'
		elif User.objects.filter(username=username).exists():
			errors['username'] = 'This username is already taken.'

		# Password validation
		if not password:
			errors['password'] = 'Password is required.'
		elif len(password) < 8:
			errors['password'] = 'Password must be at least 8 characters long.'
		elif len(password) > 128:
			errors['password'] = 'Password must be less than 128 characters.'
		elif not re.search(r'[A-Z]', password):
			errors['password'] = 'Password must contain at least one uppercase letter.'
		elif not re.search(r'[a-z]', password):
			errors['password'] = 'Password must contain at least one lowercase letter.'
		elif not re.search(r'\d', password):
			errors['password'] = 'Password must contain at least one number.'
		elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
			errors['password'] = 'Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).'

		# Phone validation (if provided)
		if phone:
			phone_pattern = r'^[0-9]{10}$'
			if not re.match(phone_pattern, phone):
				errors['phone'] = 'Please enter a valid 10-digit phone number (numbers only, no spaces or special characters).'
			elif len(phone) != 10:
				errors['phone'] = 'Phone number must be exactly 10 digits.'

		# Batches validation
		try:
			batches_num = int(batches)
			if batches_num < 0:
				errors['batches'] = 'Number of batches cannot be negative.'
			elif batches_num > 100:
				errors['batches'] = 'Number of batches cannot exceed 100.'
		except ValueError:
			errors['batches'] = 'Number of batches must be a valid number.'

		# Trainer code validation (if provided)
		if trainer_code_manual:
			if len(trainer_code_manual) > 50:
				errors['trainer_code'] = 'Trainer code must be less than 50 characters.'
			elif Trainer.objects.filter(trainer_code=trainer_code_manual).exists():
				errors['trainer_code'] = 'This trainer code is already in use.'

		# Expertise validation (if provided) - only letters and spaces allowed
		if expertise:
			expertise_pattern = r"^[a-zA-Z\s]+$"
			if not re.match(expertise_pattern, expertise):
				errors['expertise'] = 'Area of expertise can only contain letters and spaces.'
			elif len(expertise) > 255:
				errors['expertise'] = 'Area of expertise must be less than 255 characters.'

		# Bio validation (if provided)
		if bio and len(bio) > 1000:
			errors['bio'] = 'Bio must be less than 1000 characters.'

		# Assign courses validation (if provided) - only letters and spaces allowed
		if assign_courses:
			courses_pattern = r"^[a-zA-Z\s]+$"
			if not re.match(courses_pattern, assign_courses):
				errors['assign_courses'] = 'Assigned courses can only contain letters and spaces.'
			elif len(assign_courses) > 255:
				errors['assign_courses'] = 'Assigned courses must be less than 255 characters.'

		# If there are validation errors, return to form with errors
		if errors:
			return render(request, 'myapp/add_trainer.html', {
				'errors': errors,
				'form_data': {
					'full_name': full_name,
					'email': email,
					'phone': phone,
					'expertise': expertise,
					'assign_courses': assign_courses,
					'bio': bio,
					'username': username,
					'batches': batches,
					'trainer_code': trainer_code_manual,
				}
			})

		# Ensure username is unique (double check)
		base_username = username
		if User.objects.filter(username=username).exists():
			username = f"{base_username}_{trainer_code}"

		# Create user
		user = User.objects.create_user(username=username, email=email, first_name=full_name)
		user.set_password(password)
		user.save()

		# Create trainer
		trainer = Trainer.objects.create(
			user=user,
			phone=phone,
			expertise=expertise,
			assign_courses=assign_courses,
			bio=bio,
			trainer_code=trainer_code_manual or trainer_code,
			batches=int(batches),
			status='Active',
			profile_image=profile_image,
		)

		messages.success(request, f'Trainer "{full_name}" has been added successfully!')
		return redirect('add_trainer')

	# Convert Django messages to JavaScript format
	from django.contrib.messages import get_messages
	django_messages = []
	for message in get_messages(request):
		django_messages.append({
			'message': str(message),
			'type': 'error' if message.tags == 'error' else message.tags or 'success'
		})

	return render(request, 'myapp/add_trainer.html', {
		'django_messages': django_messages
	})

def course_list(request):
    courses = Course.objects.all()
    return render(request, 'myapp/course_list.html', {'courses': courses})

def admin_login(request):
	error = None
	username = ''
	if request.method == 'POST':
		username = request.POST.get('username')
		password = request.POST.get('password')
		user = authenticate(request, username=username, password=password)
		if user is not None and user.is_superuser:
			login(request, user)
			return redirect('admin_dashboard')
		else:
			error = 'Invalid credentials or not an admin.'
	return render(request, 'myapp/login/admin_login.html', {'error': error, 'username': username})



@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def trainer_list(request):
	# Get search query from request
	search_query = request.GET.get('search', '').strip()

	# Base queryset - get trainers with related user data
	trainers = Trainer.objects.select_related('user').all()

	# Apply search filter if query exists
	if search_query:
		trainers = trainers.filter(
			models.Q(user__first_name__icontains=search_query) |
			models.Q(user__last_name__icontains=search_query) |
			models.Q(user__username__icontains=search_query) |
			models.Q(user__email__icontains=search_query) |
			models.Q(expertise__icontains=search_query) |
			models.Q(assign_courses__icontains=search_query)
		)

	# Dynamic trainees count: count Trainee objects assigned to this trainer
	trainer_data = []
	for trainer in trainers:
		trainees_count = Trainee.objects.filter(course__in=Course.objects.filter(name__icontains=trainer.assign_courses)).count() if trainer.assign_courses else 0
		trainer.trainees_count = trainees_count
		trainer.status_color = '#ff3b3b' if trainer.status == 'Inactive' else '#00EA5E'
		trainer_data.append(trainer)

	total_trainers = trainers.count()
	active_trainers = trainers.filter(status__iexact='Active').count()
	total_courses = Course.objects.filter(is_active=True).count()

	return render(request, 'myapp/trainer_list.html', {
		'trainers': trainer_data,
		'total_trainers': total_trainers,
		'active_trainers': active_trainers,
		'total_courses': total_courses,
		'search_query': search_query,
	})


 

# --- ADD COURSE VIEW ---
@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def add_course(request):
	trainers = Trainer.objects.select_related('user').all()
	if request.method == 'POST':
		# Auto-generate course code
		next_id = Course.objects.count() + 1
		code = f"{next_id:03d}"

		# Get form data
		name = request.POST.get('name', '').strip()
		trainer_id = request.POST.get('trainer')
		duration = request.POST.get('duration', '').strip()
		description = request.POST.get('description', '').strip()
		learning_outcomes = request.POST.get('learning_outcomes', '').strip()
		cover_image = request.FILES.get('cover_image')
		syllabus = request.FILES.get('syllabus')
		mode = request.POST.get('mode')
		category = request.POST.get('category')

		# Validation errors dictionary
		errors = {}

		# Validate required fields
		if not name:
			errors['name'] = 'Course title is required.'
		elif len(name) < 2:
			errors['name'] = 'Course title must be at least 2 characters long.'
		elif len(name) > 255:
			errors['name'] = 'Course title must be less than 255 characters.'
		elif not name.replace(' ', '').isalpha():
			errors['name'] = 'Course title can only contain letters and spaces.'

		if not duration:
			errors['duration'] = 'Duration is required.'
		elif not duration.replace(' ', '').replace('-', '').replace(':', '').isalnum():
			errors['duration'] = 'Duration must contain only letters, numbers, spaces, hyphens, and colons.'
		elif len(duration) > 50:
			errors['duration'] = 'Duration must be less than 50 characters.'

		if not mode:
			errors['mode'] = 'Course mode is required.'

		if not category:
			errors['category'] = 'Course category is required.'

		if not trainer_id:
			errors['trainer'] = 'Trainer assignment is required.'

		if not description:
			errors['description'] = 'Course description is required.'
		elif len(description) < 10:
			errors['description'] = 'Course description must be at least 10 characters long.'
		elif len(description) > 1000:
			errors['description'] = 'Course description must be less than 1000 characters.'

		if not learning_outcomes:
			errors['learning_outcomes'] = 'Learning outcomes are required.'
		elif len(learning_outcomes) > 500:
			errors['learning_outcomes'] = 'Learning outcomes must be less than 500 characters.'

		if not syllabus:
			errors['syllabus'] = 'Course syllabus file is required.'

		# If there are validation errors, return to form with errors
		if errors:
			return render(request, 'myapp/add_course.html', {
				'trainers': trainers,
				'errors': errors,
				'form_data': {
					'name': name,
					'trainer': trainer_id,
					'duration': duration,
					'description': description,
					'learning_outcomes': learning_outcomes,
					'mode': mode,
					'category': category,
				}
			})

		# Get trainer object
		try:
			trainer = Trainer.objects.get(id=trainer_id)
		except Trainer.DoesNotExist:
			errors['trainer'] = 'Selected trainer does not exist.'
			return render(request, 'myapp/add_course.html', {
				'trainers': trainers,
				'errors': errors,
				'form_data': {
					'name': name,
					'trainer': trainer_id,
					'duration': duration,
					'description': description,
					'learning_outcomes': learning_outcomes,
					'mode': mode,
					'category': category,
				}
			})

		# Create course
		course = Course.objects.create(
			name=name,
			code=code,
			trainer=trainer,
			duration=duration,
			description=description,
			learning_outcomes=learning_outcomes,
			cover_image=cover_image,
			syllabus=syllabus,
			mode=mode,
			category=category,
		)
		request.session['show_course_success'] = True
		return redirect('add_course')

	show_course_success = request.session.pop('show_course_success', False)
	return render(request, 'myapp/add_course.html', {'trainers': trainers, 'show_course_success': show_course_success})
@user_passes_test(is_admin, login_url='/admin-login/')
def admin_dashboard(request):
	total_trainees = Trainee.objects.count()
	total_trainers = Trainer.objects.count()
	total_courses = Course.objects.filter(is_active=True).count()
	total_certificates = Certificate.objects.count()
	trainees = Trainee.objects.select_related('user', 'course').filter(user__is_superuser=False).all()[:5]
	trainee_activity = []
	for idx, trainee in enumerate(trainees, 1):
		name = trainee.user.get_full_name() or trainee.user.username
		last_login = trainee.user.last_login.strftime('%d %b %Y, %I:%M %p') if trainee.user.last_login else 'Never'
		course = trainee.course
		course_name = course.name if course else ''
		trainee_activity.append({
			'sno': f"{idx:02d}",
			'name': name,
			'last_login': last_login,
			'course': course_name,
		})
        
	# Get latest announcements
	latest_announcements = Announcement.objects.order_by('-date_posted', '-id')[:4]
	course_qs = Course.objects.filter(is_active=True)
	
	# Prepare course data with proper JSON serialization
	import json
	course_labels = []
	course_counts = []
	for course in course_qs:
		course_labels.append(course.name)
		course_counts.append(course.trainees.count())
	
	# Convert to JSON strings
	course_labels_json = json.dumps(course_labels)
	course_counts_json = json.dumps(course_counts)
	
	return render(request, 'myapp/admin_dashboard.html', {
		'user': request.user,
		'total_trainees': total_trainees,
		'total_trainers': total_trainers,
		'total_courses': total_courses,
		'total_certificates': total_certificates,
		'trainee_activity': trainee_activity,
		'course_labels': course_labels_json,
		'course_counts': course_counts_json,
		'latest_announcements': latest_announcements,
	})

def admin_logout(request):
	logout(request)
	return redirect('login_options')

def login_options(request):
	return render(request, 'myapp/login/login_options.html')

def student_login(request):
	error = None
	email = ''
	if request.method == 'POST':
		email = request.POST.get('email')
		password = request.POST.get('password')
		try:
			# First check if a trainee exists with this email
			trainee = Trainee.objects.select_related('user').get(user__email=email)
			
			# Authenticate using the associated user's credentials
			user_auth = authenticate(request, username=trainee.user.username, password=password)
			if user_auth is not None:
				login(request, user_auth)
				return redirect('trainee_dashboard')
			else:
				error = 'Invalid password.'
		except Trainee.DoesNotExist:
			error = 'No trainee found with this email.'
		except Exception as e:
			error = 'An unexpected error occurred. Please try again.'
	return render(request, 'myapp/login/student_login.html', {'user_type': 'student', 'error': error, 'email': email})

def trainer_login(request):
    error = None
    email = ''
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            # First check if a trainer exists with this email
            trainer = Trainer.objects.select_related('user').get(user__email=email)
            print(f"Found trainer: {trainer.user.username} with email: {email}")

            # Authenticate using the associated user's credentials
            user_auth = authenticate(request, username=trainer.user.username, password=password)
            if user_auth is not None:
                print("Authentication successful")
                login(request, user_auth)
                if trainer.status != 'Active':
                    messages.warning(request, 'You are currently offline. Some features may be restricted.')
                return redirect('trainer_dashboard')
            else:
                print("Authentication failed - invalid password")
                error = 'Invalid password.'
        except Trainer.DoesNotExist:
            print(f"No trainer found with email: {email}")
            error = 'No trainer found with this email.'
        except Exception as e:
            print(f"Unexpected error during login: {str(e)}")
            error = 'An unexpected error occurred. Please try again.'
    return render(request, 'myapp/login/trainer_login.html', {'user_type': 'trainer', 'error': error, 'email': email})

def trainer_logout(request):
    logout(request)
    return redirect('login_options')

@login_required(login_url='/trainer-login/')
def trainee_list_trainer(request):
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    # Get search query from request
    search_query = request.GET.get('search', '').strip()

    # Base queryset - get trainees assigned to this trainer
    trainees = Trainee.objects.filter(trainer=trainer).select_related('user', 'course')

    # Apply search filter if query exists
    if search_query:
        trainees = trainees.filter(
            models.Q(user__first_name__icontains=search_query) |
            models.Q(user__last_name__icontains=search_query) |
            models.Q(user__username__icontains=search_query) |
            models.Q(user__email__icontains=search_query) |
            models.Q(course__name__icontains=search_query) |
            models.Q(batch__icontains=search_query)
        )

    # Find all batch numbers (as integers) for this trainer
    batch_numbers = [int(t.batch) for t in trainees if t.batch and t.batch.isdigit()]
    if batch_numbers:
        min_batch = min(batch_numbers)
        max_batch = max(batch_numbers)
        all_batches = [str(i) for i in range(min_batch, max_batch + 1)]
    else:
        all_batches = ['No Batch']

    batch_dict = {batch: [] for batch in all_batches}

    for trainee in trainees:
        batch = trainee.batch or 'No Batch'

        # Calculate total tasks from all DailyAssessment records (same as update_assessment)
        from .models import DailyAssessment
        total_task = DailyAssessment.objects.filter(trainee=trainee).aggregate(total=models.Sum('score'))['total'] or 0

        completed_task = getattr(trainee, 'completed_task', 0)
        pending_completed = getattr(trainee, 'pending_completed', 0)
        daily_task = trainee.daily_task

        # Use the same remaining task calculation as update_assessment
        # The correct logic is: Remaining = (Daily incomplete) + (Previous pending)
        # Where Previous pending = Total tasks that were ever assigned minus tasks completed from pending
        daily_incomplete = max(daily_task - completed_task, 0)
        # For previous pending, we need to track what was previously pending
        # Since we don't have a "pending_assigned" field, we calculate it as:
        # Previous pending = Total assigned - Current daily tasks (since daily tasks are today's assignments)
        previous_pending = max(total_task - daily_task, 0) if total_task > daily_task else 0
        remaining_task = daily_incomplete + max(previous_pending - pending_completed, 0)

        # Get today's attendance
        today = timezone.now().date()
        today_attendance = TraineeAttendance.objects.filter(trainee=trainee, date=today).first()
        attendance_today = today_attendance.status if today_attendance else 'not_marked'

        trainee_info = {
            'id': trainee.id,
            'name': trainee.user.get_full_name() or trainee.user.username,
            'email': trainee.user.email,
            'course': trainee.course.name if trainee.course else '',
            'batch': batch,
            'total_task': total_task,
            'completed_task': trainee.completed_task,  # Show accumulated completed tasks
            'pending_completed': trainee.pending_completed,  # Show accumulated pending completed
            'remaining_task': remaining_task,
            'status': trainee.status,
            'attendance_today': attendance_today,
            'remarks': trainee.remarks or '',
        }
        batch_dict.setdefault(batch, []).append(trainee_info)

    # Pass search query to template for maintaining search state
    context = {
        'batch_dict': batch_dict,
        'search_query': search_query,
        'total_trainees': trainees.count()
    }

    return render(request, 'myapp/trainee_list_trainer.html', context)

@login_required(login_url='/trainer-login/')
def update_assessment(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    # Get current values
    current_completed = getattr(trainee, 'completed_task', 0)
    current_pending_completed = getattr(trainee, 'pending_completed', 0)
    daily_task = trainee.daily_task

    # Calculate total tasks from all DailyAssessment records
    from .models import DailyAssessment
    total_task = DailyAssessment.objects.filter(trainee=trainee).aggregate(total=models.Sum('score'))['total'] or 0

    # Calculate remaining tasks using the corrected logic:
    daily_incomplete = max(daily_task - current_completed, 0)
    previous_pending = max(total_task - daily_task, 0) if total_task > daily_task else 0
    remaining_task = daily_incomplete + max(previous_pending - current_pending_completed, 0)

    if request.method == 'POST':
        daily_task = int(request.POST.get('daily_task', trainee.daily_task))
        new_daily_completed = int(request.POST.get('completed_task', current_completed))
        new_pending_completed = int(request.POST.get('pending_completed', current_pending_completed))
        remarks = request.POST.get('remarks', '')

        # Calculate new total BEFORE creating the DailyAssessment record
        new_total_task = total_task + daily_task

        # Create a new DailyAssessment record for today's tasks
        DailyAssessment.objects.create(
            trainee=trainee,
            trainer=trainer,
            date=timezone.now().date(),
            score=daily_task,
            max_score=0,
            remarks='',
            is_completed=True
        )

        # Update trainee fields - ADD to existing values instead of replacing
        trainee.daily_task = daily_task
        trainee.completed_task = current_completed + new_daily_completed  # ADD to existing
        trainee.pending_completed = current_pending_completed + new_pending_completed  # ADD to existing
        trainee.remarks = remarks

        # Recalculate remaining tasks with corrected logic
        daily_incomplete = max(daily_task - new_daily_completed, 0)
        previous_pending = max(new_total_task - daily_task, 0) if new_total_task > daily_task else 0
        new_remaining_task = daily_incomplete + max(previous_pending - new_pending_completed, 0)

        trainee.save()
        messages.success(request, 'Task info updated!')
        return redirect('trainer_trainee_list')

    return render(request, 'myapp/update_assessment.html', {
        'trainee': trainee,
        'completed_task': current_completed,
        'pending_completed': current_pending_completed,
        'daily_task': daily_task,
        'total_task': total_task,
        'remaining_task': remaining_task,
    })

@login_required(login_url='/trainer-login/')
def trainee_attendance_trainer(request):
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    trainees = Trainee.objects.filter(trainer=trainer).select_related('user', 'course')
    # Group trainees by batch
    batch_numbers = [int(t.batch) for t in trainees if t.batch and t.batch.isdigit()]
    if batch_numbers:
        min_batch = min(batch_numbers)
        max_batch = max(batch_numbers)
        all_batches = [str(i) for i in range(min_batch, max_batch + 1)]
    else:
        all_batches = ['No Batch']
    batch_dict = {batch: [] for batch in all_batches}
    for trainee in trainees:
        batch = trainee.batch or 'No Batch'
        batch_dict.setdefault(batch, []).append(trainee)

    today = timezone.now().date()
    status_choices = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('informed', 'Informed'),
        ('not_informed', 'Not Informed'),
    ]

    if request.method == 'POST':
        for trainee in trainees:
            status = request.POST.get(f'status_{trainee.id}')
            if status:
                attendance, _ = TraineeAttendance.objects.get_or_create(trainee=trainee, date=today)

                # Handle absent with sub-type (informed/not_informed)
                if status == 'absent':
                    absent_type = request.POST.get(f'absent_type_{trainee.id}')
                    if absent_type in ['informed', 'not_informed']:
                        attendance.status = absent_type
                        remarks = request.POST.get(f'remarks_{trainee.id}', '')
                        attendance.remarks = remarks
                    else:
                        attendance.status = 'absent'
                else:
                    attendance.status = status

                attendance.save()
        messages.success(request, 'Attendance updated for all selected trainees!')
        return redirect('trainer_trainee_attendance')

    # For each trainee, get today's status if exists
    trainee_status = {}
    trainee_remarks = {}
    for trainee in trainees:
        att = TraineeAttendance.objects.filter(trainee=trainee, date=today).first()
        if att:
            trainee_status[trainee.id] = att.status
            trainee_remarks[trainee.id] = att.remarks
        else:
            trainee_status[trainee.id] = ''
            trainee_remarks[trainee.id] = ''

    return render(request, 'myapp/trainee_attendance_trainer.html', {
        'batch_dict': batch_dict,
        'status_choices': status_choices,
        'trainee_status': trainee_status,
        'trainee_remarks': trainee_remarks,
    })

@login_required(login_url='/trainer-login/')
def trainee_attendance_detail(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    # Get all attendance records for this trainee
    attendance_records = TraineeAttendance.objects.filter(trainee=trainee).order_by('-date')

    # Get trainee info for display
    trainee_info = {
        'name': trainee.user.get_full_name() or trainee.user.username,
        'email': trainee.user.email,
        'course': trainee.course.name if trainee.course else '',
        'batch': trainee.batch or 'No Batch',
    }

    # Calculate attendance statistics
    total_days = attendance_records.count()
    present_days = attendance_records.filter(status='present').count()
    absent_days = attendance_records.filter(status__in=['absent', 'informed', 'not_informed']).count()
    informed_days = attendance_records.filter(status='informed').count()
    not_informed_days = attendance_records.filter(status='not_informed').count()

    stats = {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'informed_days': informed_days,
        'not_informed_days': not_informed_days,
        'attendance_percentage': round((present_days / total_days * 100), 1) if total_days > 0 else 0,
    }

    return render(request, 'myapp/trainee_attendance_detail.html', {
        'trainee': trainee,
        'trainee_info': trainee_info,
        'attendance_records': attendance_records,
        'stats': stats,
    })

@login_required(login_url='/trainer-login/')
def upload_session(request):
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    # Get unique batches for this trainer's trainees
    trainees = Trainee.objects.filter(trainer=trainer).select_related('user', 'course')
    batches = sorted(set(trainee.batch for trainee in trainees if trainee.batch))

    # Create batch statistics with trainee counts
    batch_info_list = []
    for batch in batches:
        batch_trainees = trainees.filter(batch=batch)
        batch_info_list.append({
            'batch': batch,
            'trainee_count': batch_trainees.count()
        })

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        batch = request.POST.get('batch')
        session_url = request.POST.get('session_url')

        if title and batch and session_url:
            try:
                # Create session with current timestamp
                session = SessionRecording.objects.create(
                    title=title,
                    description=description,
                    batch=batch,
                    session_url=session_url,
                    trainer=trainer,
                    upload_status='success',
                    upload_date=timezone.now()  # Set current timestamp when uploaded
                )
                messages.success(request, f'Session "{title}" uploaded successfully!')
                return redirect('session_list')
            except Exception as e:
                SessionRecording.objects.create(
                    title=title,
                    description=description,
                    batch=batch,
                    session_url=session_url,
                    trainer=trainer,
                    upload_status='failed'
                )
                messages.error(request, f'Failed to upload session: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields.')

    return render(request, 'myapp/upload_session.html', {
        'batches': batches,
        'batch_info_list': batch_info_list,
    })

@login_required(login_url='/trainer-login/')
def session_list(request):
    # For students - show sessions for their batch
    if hasattr(request.user, 'trainee'):
        trainee = request.user.trainee
        batch = trainee.batch
        sessions = SessionRecording.objects.filter(batch=batch, is_active=True).order_by('-upload_date')
        return render(request, 'myapp/session_list.html', {
            'sessions': sessions,
            'batch': batch,
        })

    # For trainers - show all their sessions with batch-wise stats
    elif hasattr(request.user, 'trainer'):
        trainer = request.user.trainer
        sessions = SessionRecording.objects.filter(trainer=trainer).order_by('-upload_date')

        # Get batch-wise statistics
        batch_stats = {}
        for session in sessions:
            if session.batch not in batch_stats:
                batch_stats[session.batch] = {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'pending': 0
                }
            batch_stats[session.batch]['total'] += 1
            batch_stats[session.batch][session.upload_status] += 1

        return render(request, 'myapp/session_list_trainer.html', {
            'sessions': sessions,
            'batch_stats': batch_stats,
        })

    return redirect('login_options')

@login_required(login_url='/trainer-login/')
def session_detail(request, session_id):
    """Show detailed view of a specific session"""
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    try:
        session = SessionRecording.objects.get(id=session_id, trainer=trainer)
    except SessionRecording.DoesNotExist:
        messages.error(request, 'Session not found or access denied.')
        return redirect('session_list')

    # Get related sessions from the same batch
    related_sessions = SessionRecording.objects.filter(
        batch=session.batch,
        trainer=trainer,
        is_active=True
    ).exclude(id=session_id).order_by('-upload_date')[:5]

    return render(request, 'myapp/session_detail.html', {
        'session': session,
        'related_sessions': related_sessions,
    })

@login_required(login_url='/trainer-login/')
def delete_session(request, session_id):
    """Delete a specific session recording"""
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    try:
        session = SessionRecording.objects.get(id=session_id, trainer=trainer)
    except SessionRecording.DoesNotExist:
        messages.error(request, 'Session not found or access denied.')
        return redirect('session_list')

    if request.method == 'POST':
        session_title = session.title
        session.delete()
        messages.success(request, f'Session "{session_title}" has been deleted successfully.')
        return redirect('session_list')

    return render(request, 'myapp/delete_session.html', {
        'session': session,
    })

@login_required(login_url='/trainer-login/')
def toggle_session_visibility(request, session_id):
    """Toggle visibility of a session recording"""
    trainer = getattr(request.user, 'trainer', None)
    if not trainer:
        return redirect('trainer_login')

    try:
        session = SessionRecording.objects.get(id=session_id, trainer=trainer)
    except SessionRecording.DoesNotExist:
        messages.error(request, 'Session not found or access denied.')
        return redirect('session_list')

    if request.method == 'POST':
        session.is_visible = not session.is_visible
        session.save()
        status = 'visible' if session.is_visible else 'hidden'
        messages.success(request, f'Session "{session.title}" is now {status}.')
        return redirect('session_detail', session_id=session.id)

    return redirect('session_list')


@login_required
def student_certificates(request):
    """Student certificate page - shows all certificates earned by the student"""
    trainee = getattr(request.user, 'trainee', None)
    if not trainee:
        return redirect('student_login')

    # Get all certificates for this student
    certificates = Certificate.objects.filter(trainee=trainee).select_related('course').order_by('-issued_date')

    # Check if student has completed their course (for certificate generation)
    course_completed = False
    if trainee.course and trainee.progress >= 80:  # 80% progress threshold
        course_completed = True
        # Check if certificate already exists
        existing_cert = certificates.filter(course=trainee.course).first()
        if not existing_cert:
            # Generate certificate if student completed course
            Certificate.objects.create(
                trainee=trainee,
                course=trainee.course,
                completion_percentage=trainee.progress,
                grade='A' if trainee.progress >= 90 else 'B' if trainee.progress >= 80 else 'C'
            )
            # Refresh certificates
            certificates = Certificate.objects.filter(trainee=trainee).select_related('course').order_by('-issued_date')

    context = {
        'trainee': trainee,
        'certificates': certificates,
        'course_completed': course_completed,
        'total_certificates': certificates.count()
    }

    return render(request, 'myapp/student_certificates.html', context)

@login_required
@user_passes_test(is_admin, login_url='/admin-login/')
def admin_certificates(request):
    """Admin certificate management page - shows all certificates in the system with management features"""
    # Get all certificates with related data
    certificates = Certificate.objects.select_related('trainee__user', 'course').filter(trainee__user__is_superuser=False).order_by('-issued_date')

    # Add serial numbers for display
    certificates_with_sno = []
    for idx, cert in enumerate(certificates, 1):
        certificates_with_sno.append({
            'sno': idx,
            'certificate': cert,
            'trainee_name': cert.trainee.user.get_full_name() or cert.trainee.user.username,
            'course_name': cert.course.name if cert.course else 'N/A',
            'certificate_id': cert.certificate_number,
            'issue_date': cert.issued_date,
            'status': 'Verified' if cert.is_verified else 'Pending',
            'completion_percentage': cert.completion_percentage,
            'grade': cert.grade
        })

    # Calculate statistics
    total_certificates = certificates.count()
    verified_certificates = certificates.filter(is_verified=True).count()
    pending_certificates = total_certificates - verified_certificates

    # Get recent certificates (last 10)
    recent_certificates = certificates[:10]

    # Get certificate distribution by grade
    grade_distribution = {
        'A': certificates.filter(grade='A').count(),
        'B': certificates.filter(grade='B').count(),
        'C': certificates.filter(grade='C').count(),
        'D': certificates.filter(grade='D').count(),
        'F': certificates.filter(grade='F').count(),
    }

    # Get certificates by course
    course_stats = []
    for course in Course.objects.filter(is_active=True):
        course_cert_count = certificates.filter(course=course).count()
        if course_cert_count > 0:
            course_stats.append({
                'name': course.name,
                'count': course_cert_count,
                'code': course.code
            })

    # Check if certificate template exists
    template_path = os.path.join(settings.MEDIA_ROOT, 'certificate_templates', 'certificate_template.png')
    template_exists = os.path.exists(template_path)
    current_template = 'certificate_template.png' if template_exists else None

    if request.method == 'POST':
        action = request.POST.get('action')
        certificate_id = request.POST.get('certificate_id')

        if action == 'generate':
            # Generate certificate for a trainee
            trainee_id = request.POST.get('trainee_id')
            course_id = request.POST.get('course_id')
            completion_percentage = request.POST.get('completion_percentage', 100)
            grade = request.POST.get('grade', 'A')

            try:
                trainee = Trainee.objects.get(id=trainee_id)
                course = Course.objects.get(id=course_id)

                # Check if certificate already exists
                existing_cert = Certificate.objects.filter(trainee=trainee, course=course).first()
                if existing_cert:
                    messages.error(request, f'Certificate already exists for {trainee.user.get_full_name()} in {course.name}')
                else:
                    # Create new certificate
                    certificate = Certificate.objects.create(
                        trainee=trainee,
                        course=course,
                        completion_percentage=int(completion_percentage),
                        grade=grade,
                        is_verified=True
                    )

                    # Generate certificate image
                    certificate_path = generate_certificate_image({
                        'student_name': trainee.user.get_full_name() or trainee.user.username,
                        'course_name': course.name,
                        'completion_percentage': int(completion_percentage),
                        'completion_date': certificate.issued_date.strftime('%B %d, %Y'),
                        'grade': grade,
                        'certificate_id': certificate.certificate_number
                    })

                    if certificate_path:
                        messages.success(request, f'Certificate generated and image created for {trainee.user.get_full_name()} in {course.name}')
                    else:
                        messages.warning(request, f'Certificate generated for {trainee.user.get_full_name()} in {course.name}, but image creation failed')

                    return redirect('admin_certificates')

            except (Trainee.DoesNotExist, Course.DoesNotExist) as e:
                messages.error(request, 'Invalid trainee or course selection')

        elif action == 'delete' and certificate_id:
            try:
                certificate = Certificate.objects.get(id=certificate_id)
                certificate.delete()
                messages.success(request, 'Certificate deleted successfully!')
                return redirect('admin_certificates')
            except Certificate.DoesNotExist:
                messages.error(request, 'Certificate not found!')

        elif action == 'upload_template':
            template_file = request.FILES.get('template_file')
            if template_file:
                # Ensure certificate_templates directory exists
                template_dir = os.path.join(settings.MEDIA_ROOT, 'certificate_templates')
                os.makedirs(template_dir, exist_ok=True)

                # Save the uploaded template
                template_path = os.path.join(template_dir, 'certificate_template.png')
                with open(template_path, 'wb+') as destination:
                    for chunk in template_file.chunks():
                        destination.write(chunk)

                messages.success(request, 'Certificate template uploaded successfully!')
                return redirect('admin_certificates')
            else:
                messages.error(request, 'Please select a template file to upload.')

        elif action == 'upload_student_cert':
            trainee_id = request.POST.get('trainee_id')
            certificate_file = request.FILES.get('certificate_file')

            if not trainee_id or not certificate_file:
                messages.error(request, 'Please select a trainee and certificate file.')
                return redirect('admin_certificates')

            try:
                trainee = Trainee.objects.get(id=trainee_id)

                # Create certificate directory if it doesn't exist
                cert_dir = os.path.join(settings.MEDIA_ROOT, 'certificates')
                os.makedirs(cert_dir, exist_ok=True)

                # Save the uploaded certificate file
                fs = FileSystemStorage(location=cert_dir)
                filename = fs.save(f"uploaded_cert_{trainee.id}_{certificate_file.name}", certificate_file)
                # Use the actual saved filename (which includes hash if needed)
                saved_filename = fs.get_valid_name(filename)

                # Create certificate record in database
                certificate = Certificate.objects.create(
                    trainee=trainee,
                    course=trainee.course,
                    completion_percentage=100,  # Default to 100% for uploaded certificates
                    grade='A',  # Default grade
                    is_verified=True,
                    certificate_file=saved_filename  # Store the file path
                )

                messages.success(request, f'Certificate uploaded successfully for {trainee.user.get_full_name()}!')
                return redirect('admin_certificates')

            except Trainee.DoesNotExist:
                messages.error(request, 'Trainee not found!')
            except Exception as e:
                messages.error(request, f'Error uploading certificate: {str(e)}')

        elif action == 'delete_trainee_certificates':
            trainee_id = request.POST.get('trainee_id')

            if not trainee_id:
                messages.error(request, 'Trainee ID is required.')
                return redirect('admin_certificates')

            try:
                trainee = Trainee.objects.get(id=trainee_id)
                certificates = Certificate.objects.filter(trainee=trainee)

                # Delete certificate files from storage
                for cert in certificates:
                    if cert.certificate_file:
                        file_path = os.path.join(settings.MEDIA_ROOT, 'certificates', cert.certificate_file.name)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except OSError as e:
                                messages.error(request, f'Error deleting certificate file: {str(e)}')
                            except Exception as e:
                                messages.error(request, f'Error deleting certificate file: {str(e)}')

            except Trainee.DoesNotExist:
                messages.error(request, 'Trainee not found!')
            except Exception as e:
                messages.error(request, f'Error deleting certificates: {str(e)}')

    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    course_filter = request.GET.get('course', '').strip()
    batch_filter = request.GET.get('batch', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Get all trainees with their certificate information and apply filters
    trainees = Trainee.objects.select_related('user', 'course').filter(user__is_superuser=False).all()

    # Apply search filters
    if search_query:
        trainees = trainees.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    if course_filter:
        trainees = trainees.filter(course_id=course_filter)

    if batch_filter:
        trainees = trainees.filter(batch__icontains=batch_filter)

    if status_filter:
        trainees = trainees.filter(status=status_filter)

    # Add certificate information for each trainee
    trainees_with_certificates = []
    for trainee in trainees:
        # Get certificates for this trainee
        certificates = Certificate.objects.filter(trainee=trainee).select_related('course')

        trainees_with_certificates.append({
            'trainee': trainee,
            'certificates': certificates,
            'certificate_count': certificates.count(),
            'has_certificate': certificates.exists()
        })

    # Get trainees and courses for the generate certificate form (keeping existing functionality)
    active_trainees = Trainee.objects.select_related('user', 'course').filter(status='Active', user__is_superuser=False)
    courses = Course.objects.filter(is_active=True)

    context = {
        'certificates': certificates_with_sno,
        'total_certificates': total_certificates,
        'verified_certificates': verified_certificates,
        'pending_certificates': pending_certificates,
        'recent_certificates': recent_certificates,
        'grade_distribution': grade_distribution,
        'course_stats': course_stats,
        'trainees_with_certificates': trainees_with_certificates,
        'trainees': active_trainees,
        'courses': courses,
        'template_exists': template_exists,
        'current_template': current_template,
        # Search parameters for form persistence
        'search_query': search_query,
        'course_filter': course_filter,
        'batch_filter': batch_filter,
        'status_filter': status_filter,
    }

    return render(request, 'myapp/admin_certificates.html', context)

@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def course_list(request):
    """Admin course list view with search functionality"""
    # Get search query from request
    search_query = request.GET.get('search', '').strip()

    # Base queryset - get all courses
    courses = Course.objects.select_related('trainer__user').all()

    # Apply search filter if query exists
    if search_query:
        courses = courses.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(mode__icontains=search_query) |
            Q(trainer__user__first_name__icontains=search_query) |
            Q(trainer__user__last_name__icontains=search_query) |
            Q(trainer__user__username__icontains=search_query)
        )

    # Pass search query to template for maintaining search state
    context = {
        'courses': courses,
        'search_query': search_query,
        'total_courses': courses.count()
    }

    return render(request, 'myapp/course_list.html', context)


@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def trainee_certificates(request, trainee_id):
    """View for individual trainee certificate management"""
    try:
        trainee = Trainee.objects.select_related('user', 'course').get(id=trainee_id)
    except Trainee.DoesNotExist:
        messages.error(request, 'Trainee not found!')
        return redirect('admin_certificates')

    # Get all certificates for this trainee
    certificates = Certificate.objects.filter(trainee=trainee).select_related('course').order_by('-issued_date')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'upload_certificate':
            certificate_file = request.FILES.get('certificate_file')
            course_id = request.POST.get('course_id')

            if not certificate_file or not course_id:
                messages.error(request, 'Please select a certificate file and course.')
                return redirect('trainee_certificates', trainee_id=trainee_id)

            try:
                course = Course.objects.get(id=course_id)

                certificate = Certificate.objects.create(
                    trainee=trainee,
                    course=course,
                    completion_percentage=100,
                    grade='A',
                    is_verified=True,
                    certificate_file=certificate_file
                )

                messages.success(request, f'Certificate uploaded successfully for {trainee.user.get_full_name()}!')
                return redirect('trainee_certificates', trainee_id=trainee_id)

            except Course.DoesNotExist:
                messages.error(request, 'Course not found!')
            except Exception as e:
                messages.error(request, f'Error uploading certificate: {str(e)}')

        elif action == 'delete_certificate':
            certificate_id = request.POST.get('certificate_id')

            if not certificate_id:
                messages.error(request, 'Certificate ID is required.')
                return redirect('trainee_certificates', trainee_id=trainee_id)

            try:
                certificate = Certificate.objects.get(id=certificate_id, trainee=trainee)

                if certificate.certificate_file:
                    file_path = os.path.join(settings.MEDIA_ROOT, 'certificates', certificate.certificate_file.name)
                    if os.path.exists(file_path):
                        os.remove(file_path)

                certificate.delete()

                messages.success(request, f'Certificate deleted successfully!')
                return redirect('trainee_certificates', trainee_id=trainee_id)

            except Certificate.DoesNotExist:
                messages.error(request, 'Certificate not found!')
            except Exception as e:
                messages.error(request, f'Error deleting certificate: {str(e)}')

    courses = Course.objects.filter(is_active=True)

    context = {
        'trainee': trainee,
        'certificates': certificates,
        'courses': courses,
        'certificate_count': certificates.count()
    }

    return render(request, 'myapp/trainee_certificates.html', context)


@login_required(login_url='/admin-login/')
@user_passes_test(is_admin, login_url='/admin-login/')
def download_certificate(request, certificate_id):
    """Download certificate image"""
    try:
        certificate = Certificate.objects.get(id=certificate_id)

        # Generate certificate image if it doesn't exist
        certificate_path = generate_certificate_image({
            'student_name': certificate.trainee.user.get_full_name() or certificate.trainee.user.username,
            'course_name': certificate.course.name if certificate.course else 'Course',
            'completion_percentage': certificate.completion_percentage,
            'completion_date': certificate.issued_date.strftime('%B %d, %Y'),
            'grade': certificate.grade,
            'certificate_id': certificate.certificate_number
        })

        if certificate_path and os.path.exists(certificate_path):
            # Serve the file for download
            with open(certificate_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='image/png')
                response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.certificate_number}.png"'
                return response
        else:
            messages.error(request, 'Certificate image not found. Please regenerate the certificate.')
            return redirect('admin_certificates')

    except Certificate.DoesNotExist:
        messages.error(request, 'Certificate not found!')
        return redirect('admin_certificates')
    except Exception as e:
        messages.error(request, f'Error downloading certificate: {str(e)}')
        return redirect('admin_certificates')


@login_required(login_url='/student-login/')
def trainee_dashboard(request):
    """Trainee dashboard with activity tracking and statistics"""
    trainee = getattr(request.user, 'trainee', None)
    if not trainee:
        return redirect('student_login')
    
    # Get trainee's certificates
    certificates = Certificate.objects.filter(trainee=trainee).select_related('course')
    
    # Get trainee's course
    course = trainee.course
    
    # Calculate task statistics from trainer updates
    from .models import DailyAssessment
    today = timezone.now().date()

    # Get today's task assignment from trainer
    today_assessment = DailyAssessment.objects.filter(trainee=trainee, date=today).first()
    daily_task_assigned = today_assessment.score if today_assessment else 0

    # Get total tasks assigned by trainer (sum of all DailyAssessment scores)
    total_tasks_assigned = DailyAssessment.objects.filter(trainee=trainee).aggregate(total=models.Sum('score'))['total'] or 0

    # Get completed tasks (from trainee.completed_task field)
    completed_tasks = getattr(trainee, 'completed_task', 0)

    # Calculate pending tasks correctly
    pending_tasks = max(total_tasks_assigned - completed_tasks, 0)

    # Get task completion rate
    task_completion_rate = (completed_tasks / total_tasks_assigned * 100) if total_tasks_assigned > 0 else 0

    # Get recent task updates (last 7 days)
    recent_task_updates = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_assessment = DailyAssessment.objects.filter(trainee=trainee, date=day).first()
        if day_assessment:
            recent_task_updates.append({
                'date': day.strftime('%a'),
                'assigned': day_assessment.score,
                'completed': min(day_assessment.score, completed_tasks),  # Can't complete more than assigned
                'status': 'completed' if completed_tasks >= day_assessment.score else 'pending'
            })
        else:
            recent_task_updates.append({
                'date': day.strftime('%a'),
                'assigned': 0,
                'completed': 0,
                'status': 'no-task'
            })

    # Get task statistics for display
    task_stats = {
        'today_assigned': daily_task_assigned,
        'today_completed': min(daily_task_assigned, completed_tasks),
        'total_assigned': total_tasks_assigned,
        'total_completed': completed_tasks,
        'pending': pending_tasks,
        'completion_rate': round(task_completion_rate, 1)
    }
    
    # Get attendance statistics
    total_attendance = TraineeAttendance.objects.filter(trainee=trainee).count()
    present_days = TraineeAttendance.objects.filter(trainee=trainee, status='present').count()
    attendance_percentage = round((present_days / total_attendance * 100), 1) if total_attendance > 0 else 0
    
    # Get recent activities (last 5)
    recent_assessments = DailyAssessment.objects.filter(trainee=trainee).order_by('-date')[:5]
    recent_attendance = TraineeAttendance.objects.filter(trainee=trainee).order_by('-date')[:5]
    
    # Get session recordings for trainee's batch (trainer uploaded sessions)
    if trainee.batch:
        sessions = SessionRecording.objects.filter(
            batch=trainee.batch,
            is_active=True,
            is_visible=True  # Only show sessions that are visible to trainees
        ).select_related('trainer__user').order_by('-upload_date')[:3]
    else:
        sessions = []  # No sessions if no batch assigned
    
    # Calculate leaderboard position (based on progress)
    all_trainees = Trainee.objects.filter(course=course).order_by('-progress') if course else []
    leaderboard_position = 0
    for idx, t in enumerate(all_trainees, 1):
        if t.id == trainee.id:
            leaderboard_position = idx
            break
    
    # Get weekly activity data (last 7 days) - based on attendance
    today = timezone.now().date()
    weekly_activity = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        # Get attendance for this day
        attendance = TraineeAttendance.objects.filter(trainee=trainee, date=day).first()
        attendance_score = 100 if attendance and attendance.status == 'present' else 0

        weekly_activity.append({
            'day': day.strftime('%a'),
            'score': attendance_score
        })

    # Calculate correct day names for the mini-calendar display
    # Show last 7 days (today-6 to today) for attendance history
    calendar_day_names = []
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        calendar_day_names.append(day_date.strftime('%a'))
    
    # Get monthly attendance activity (last 12 months)
    import json
    from datetime import datetime
    monthly_attendance = []
    for i in range(11, -1, -1):
        month_date = today - timedelta(days=i*30)
        month_start = month_date.replace(day=1)
        if i > 0:
            next_month = today - timedelta(days=(i-1)*30)
            month_end = next_month.replace(day=1)
        else:
            month_end = today
        
        # Get attendance for this month
        month_attendance = TraineeAttendance.objects.filter(
            trainee=trainee,
            date__gte=month_start,
            date__lt=month_end
        )
        present_count = month_attendance.filter(status='present').count()
        total_count = month_attendance.count()
        attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0
        
        monthly_attendance.append({
            'month': month_start.strftime('%b'),
            'attendance': round(attendance_rate, 1)
        })
    
    # Get attendance summary for charts
    present_count = TraineeAttendance.objects.filter(trainee=trainee, status='present').count()
    absent_count = TraineeAttendance.objects.filter(trainee=trainee, status='absent').count()
    total_attendance_days = present_count + absent_count
    
    # Get recent announcements for trainees (last 3)
    recent_announcements = Announcement.objects.filter(
        models.Q(target_audience='all') | models.Q(target_audience='trainees')
    ).order_by('-date_posted')[:3]

    # Get ALL announcements for trainees to calculate real unread count
    all_trainee_announcements = Announcement.objects.filter(
        models.Q(target_audience='all') | models.Q(target_audience='trainees')
    ).order_by('-date_posted', '-id')

    # Get unread announcement count (based on session tracking)
    viewed_announcements = request.session.get('viewed_announcements', [])
    unread_announcements_count = len([ann for ann in all_trainee_announcements if ann.id not in viewed_announcements])
    
    # Prepare data for charts
    weekly_labels = [day['day'] for day in weekly_activity]
    weekly_scores = [day['score'] for day in weekly_activity]
    monthly_labels = [month['month'] for month in monthly_attendance]
    monthly_attendance_data = [month['attendance'] for month in monthly_attendance]
    attendance_labels = ['Present', 'Absent']
    attendance_data = [present_count, absent_count]
    
    context = {
        'trainee': trainee,
        'course': course,
        'certificates': certificates,
        'task_stats': task_stats,
        'recent_task_updates': recent_task_updates,
        'attendance_percentage': attendance_percentage,
        'present_days': present_count,
        'absent_days': absent_count,
        'leaderboard_position': leaderboard_position,
        'recent_assessments': recent_assessments,
        'recent_attendance': recent_attendance,
        'sessions': sessions,
        'recent_announcements': recent_announcements,
        'unread_announcements_count': unread_announcements_count,
        'calendar_day_names': calendar_day_names,
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_scores': json.dumps(weekly_scores),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_attendance': json.dumps(monthly_attendance_data),
        'attendance_labels': json.dumps(attendance_labels),
        'attendance_data': json.dumps(attendance_data),
    }
    
    return render(request, 'myapp/trainee_dashboard.html', context)


@login_required
def my_courses(request):
    """View for trainee's enrolled courses with session recordings"""
    trainee = get_object_or_404(Trainee, user=request.user)

    # Get enrolled courses
    enrolled_courses = Course.objects.filter(trainees=trainee, is_active=True)

    # For each course, get session recordings and other stats
    courses_data = []
    all_sessions = []

    for course in enrolled_courses:
        # Get session recordings for this course (by matching batch or course)
        course_sessions = SessionRecording.objects.filter(
            Q(batch=trainee.batch) | Q(title__icontains=course.name),
            is_active=True,
            is_visible=True
        ).select_related('trainer__user').order_by('-upload_date')[:5]  # Last 5 sessions

        # Add course name to each session for the separate section
        for session in course_sessions:
            session.course_name = course.name
            all_sessions.append(session)

        # Get course statistics
        total_tasks = trainee.total_task if course == trainee.course else 0
        completed_tasks = trainee.completed_task if course == trainee.course else 0
        progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        courses_data.append({
            'course': course,
            'sessions': course_sessions,
            'total_sessions': course_sessions.count(),
            'progress_percentage': round(progress_percentage, 1),
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'enrollment_date': trainee.user.date_joined.date() if trainee.user.date_joined else None
        })

    context = {
        'trainee': trainee,
        'courses_data': courses_data,
        'total_enrolled_courses': len(courses_data),
        'all_sessions': all_sessions,  # All sessions for the separate section
    }

    return render(request, 'myapp/courses.html', context)


def student_logout(request):
    logout(request)
    return redirect('login_options')
