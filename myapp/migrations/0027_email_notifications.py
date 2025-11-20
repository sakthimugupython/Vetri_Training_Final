from django.db import migrations, models
import django.db.models.deletion
import uuid


def create_notification_defaults(apps, schema_editor):
    Trainee = apps.get_model('myapp', 'Trainee')
    NotificationPreference = apps.get_model('myapp', 'NotificationPreference')
    EmailTemplate = apps.get_model('myapp', 'EmailTemplate')

    for trainee in Trainee.objects.all():
        NotificationPreference.objects.get_or_create(
            trainee=trainee,
            defaults={
                'allow_announcements': True,
                'allow_attendance_updates': True,
                'allow_task_updates': True,
                'allow_session_material': True,
                'unsubscribed': False,
            },
        )

    EmailTemplate.objects.get_or_create(
        slug='announcement_generic',
        defaults={
            'name': 'Announcement Notification',
            'subject_template': 'New announcement: {{ title }}',
            'body_template': (
                'Hello {{ trainee_name }},\n\n'
                'A new announcement has been posted by {{ posted_by }}.\n'
                'Title: {{ title }}\n\n'
                '{% if short_description %}{{ short_description }}\n\n{% endif %}'
                '{{ content }}\n\n'
                'View more details in the trainee portal.\n\n'
                'If you no longer wish to receive these updates, you can unsubscribe here: {{ unsubscribe_url }}\n'
            ),
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0026_certificate_certificate_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(unique=True)),
                ('name', models.CharField(max_length=100)),
                ('subject_template', models.TextField()),
                ('body_template', models.TextField(help_text='Use Django template syntax. Available context varies per notification type.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allow_announcements', models.BooleanField(default=True)),
                ('allow_attendance_updates', models.BooleanField(default=True)),
                ('allow_task_updates', models.BooleanField(default=True)),
                ('allow_session_material', models.BooleanField(default=True)),
                ('unsubscribed', models.BooleanField(default=False)),
                ('unsubscribe_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('trainee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to='myapp.trainee')),
            ],
        ),
        migrations.CreateModel(
            name='EmailNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('announcement', 'Announcement'), ('attendance', 'Attendance Update'), ('task', 'Task Update'), ('session', 'Session Material Upload')], max_length=30)),
                ('recipient_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('context', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('sent', 'Sent'), ('failed', 'Failed'), ('bounced', 'Bounced')], default='queued', max_length=20)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('max_attempts', models.PositiveIntegerField(default=3)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('message_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='myapp.emailtemplate')),
                ('trainee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_notifications', to='myapp.trainee')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(create_notification_defaults, migrations.RunPython.noop),
    ]
