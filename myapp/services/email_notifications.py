import logging
from datetime import date, datetime, time
from typing import Iterable, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Context, Template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from myapp.models import (
    EmailNotification,
    EmailTemplate,
    NotificationPreference,
    SessionRecording,
    Trainee,
    Trainer,
)

logger = logging.getLogger(__name__)


class EmailNotificationService:
    RETRY_DELAY_MINUTES = 15

    def __init__(self, *, connection=None):
        self.connection = connection or get_connection()

    # Core API --------------------------------------------------------------
    def queue_announcement_notification(self, announcement, *, recipients: Iterable[Trainee]):
        template = self._get_template('announcement_generic')
        timestamp_dt = self._normalize_timestamp(announcement.date_posted)
        timestamp_iso = timestamp_dt.isoformat()
        timestamp_display = self._format_timestamp(timestamp_dt)
        notifications = []

        for trainee in recipients:
            pref = self._get_preferences(trainee)
            if not self._should_notify(pref, 'allow_announcements'):
                continue

            context = {
                'title': announcement.title,
                'short_description': announcement.short_description,
                'content': announcement.content,
                'posted_by': announcement.posted_by,
                'timestamp': timestamp_display,
                'timestamp_iso': timestamp_iso,
                'trainee_name': trainee.user.get_full_name() or trainee.user.username,
                'intro': f"A new announcement has been posted by {announcement.posted_by}.",
                'summary': announcement.short_description or announcement.content,
                'changes': [],
                'trainer_name': announcement.posted_by,
            }

            notification = self._create_notification(
                trainee=trainee,
                notification_type=EmailNotification.NotificationType.ANNOUNCEMENT,
                template=template,
                context=context,
            )
            if notification:
                notifications.append(notification)

        self._send_batch(notifications)
        return notifications

    def queue_task_update_notification(
        self,
        *,
        trainee: Trainee,
        trainer: Optional[Trainer],
        summary: Optional[str] = None,
        changes: Optional[Iterable[str]] = None,
        assigned_today: Optional[int] = None,
        completed_since_last: Optional[int] = None,
        total_assigned: Optional[int] = None,
        total_completed: Optional[int] = None,
        remaining_task: Optional[int] = None,
        remarks: Optional[str] = None,
        event_timestamp: Optional[datetime] = None,
    ) -> Optional[EmailNotification]:
        pref = self._get_preferences(trainee)
        if not self._should_notify(pref, 'allow_task_updates'):
            return None

        trainer_name = None
        if trainer and getattr(trainer, 'user', None):
            trainer_name = trainer.user.get_full_name() or trainer.user.username

        template = self._get_template('task_update')
        timestamp_dt = self._normalize_timestamp(event_timestamp or timezone.now())
        context = {
            'title': f"Task update from {trainer_name or 'your trainer'}",
            'summary': summary or 'Your trainer updated your daily task plan.',
            'intro': f"{trainer_name or 'Your trainer'} updated your daily task schedule.",
            'changes': list(changes or []),
            'assigned_today': assigned_today,
            'completed_since_last': completed_since_last,
            'total_assigned': total_assigned,
            'total_completed': total_completed,
            'remaining_task': remaining_task,
            'remarks': remarks,
            'timestamp': self._format_timestamp(timestamp_dt),
            'timestamp_iso': timestamp_dt.isoformat(),
            'trainee_name': trainee.user.get_full_name() or trainee.user.username,
            'trainer_name': trainer_name,
        }

        notification = self._create_notification(
            trainee=trainee,
            notification_type=EmailNotification.NotificationType.TASK,
            template=template,
            context=context,
        )
        if not notification:
            return None

        self._send_batch([notification])
        return notification

    def queue_attendance_notification(
        self,
        *,
        trainee: Trainee,
        trainer: Optional[Trainer],
        attendance_date,
        status: str,
        previous_status: Optional[str] = None,
        remarks: Optional[str] = None,
        previous_remarks: Optional[str] = None,
        event_timestamp: Optional[datetime] = None,
    ) -> Optional[EmailNotification]:
        pref = self._get_preferences(trainee)
        if not self._should_notify(pref, 'allow_attendance_updates'):
            return None

        trainer_name = None
        if trainer and getattr(trainer, 'user', None):
            trainer_name = trainer.user.get_full_name() or trainer.user.username

        template = self._get_template('attendance_update')
        timestamp_dt = self._normalize_timestamp(event_timestamp or timezone.now())
        status_display = (status or '').replace('_', ' ').title()
        changes = []
        if previous_status and previous_status != status:
            prev_display = previous_status.replace('_', ' ').title()
            changes.append(f"Attendance status changed from {prev_display} to {status_display}")
        if (previous_remarks or '') != (remarks or ''):
            if remarks:
                changes.append(f"Trainer remarks updated: {remarks}")
            else:
                changes.append("Trainer cleared previous attendance remarks")

        date_display = attendance_date.strftime('%d %b %Y') if hasattr(attendance_date, 'strftime') else str(attendance_date)

        context = {
            'title': f"Attendance update for {date_display}",
            'summary': f"Attendance marked as {status_display} on {date_display}.",
            'intro': f"{trainer_name or 'Your trainer'} updated your attendance record.",
            'changes': changes,
            'attendance_status': status_display,
            'attendance_date': date_display,
            'remarks': remarks,
            'timestamp': self._format_timestamp(timestamp_dt),
            'timestamp_iso': timestamp_dt.isoformat(),
            'trainee_name': trainee.user.get_full_name() or trainee.user.username,
            'trainer_name': trainer_name,
        }

        notification = self._create_notification(
            trainee=trainee,
            notification_type=EmailNotification.NotificationType.ATTENDANCE,
            template=template,
            context=context,
        )
        if not notification:
            return None

        self._send_batch([notification])
        return notification

    def queue_session_material_notification(
        self,
        *,
        session: SessionRecording,
        recipients: Iterable[Trainee],
    ) -> Iterable[EmailNotification]:
        timestamp_dt = self._normalize_timestamp(session.upload_date)
        trainer = session.trainer
        trainer_name = None
        if trainer and getattr(trainer, 'user', None):
            trainer_name = trainer.user.get_full_name() or trainer.user.username

        template = self._get_template('session_material')
        notifications = []

        for trainee in recipients:
            pref = self._get_preferences(trainee)
            if not self._should_notify(pref, 'allow_session_material'):
                continue

            context = {
                'title': session.title,
                'summary': session.description or f"A new session recording has been uploaded for batch {session.batch}.",
                'intro': f"{trainer_name or 'Your trainer'} uploaded a new session recording for batch {session.batch}.",
                'changes': [],
                'session_description': session.description,
                'session_batch': session.batch,
                'session_url': session.session_url,
                'timestamp': self._format_timestamp(timestamp_dt),
                'timestamp_iso': timestamp_dt.isoformat(),
                'trainee_name': trainee.user.get_full_name() or trainee.user.username,
                'trainer_name': trainer_name,
            }

            notification = self._create_notification(
                trainee=trainee,
                notification_type=EmailNotification.NotificationType.SESSION,
                template=template,
                context=context,
            )
            if notification:
                notifications.append(notification)

        self._send_batch(notifications)
        return notifications

    # Helpers --------------------------------------------------------------
    def _create_notification(self, *, trainee: Trainee, notification_type: str, template: Optional[EmailTemplate], context: dict) -> Optional[EmailNotification]:
        email = trainee.user.email
        if not email:
            logger.debug("Skipping notification for %s; trainee has no email", trainee)
            return None

        subject = self._render_subject(template, context)
        body_text = self._render_body(template, context)

        notification = EmailNotification.objects.create(
            trainee=trainee,
            notification_type=notification_type,
            recipient_email=email,
            subject=subject,
            body=body_text,
            context=context,
            template=template,
        )
        return notification

    def _send_batch(self, notifications: Iterable[EmailNotification]) -> None:
        messages = []
        for notification in notifications:
            try:
                message = EmailMultiAlternatives(
                    subject=notification.subject,
                    body=notification.body,
                    from_email=self._from_email(),
                    to=[notification.recipient_email],
                    connection=self.connection,
                )
                messages.append((notification, message))
            except Exception as exc:  # pragma: no cover - instantiation failure
                logger.exception("Failed to build email for notification %s: %s", notification.pk, exc)
                notification.mark_failed(str(exc))

        if not messages:
            return

        try:
            self.connection.send_messages([msg for _, msg in messages])
        except Exception as exc:  # pragma: no cover - SMTP failure
            logger.exception("Bulk email send failed: %s", exc)
            for notification, _ in messages:
                notification.attempt_count += 1
                notification.last_attempt_at = timezone.now()
                if notification.can_retry:
                    notification.save(update_fields=['attempt_count', 'last_attempt_at'])
                else:
                    notification.mark_failed(str(exc))
        else:
            sent_at = timezone.now()
            for notification, _ in messages:
                notification.status = EmailNotification.Status.SENT
                notification.attempt_count += 1
                notification.last_attempt_at = sent_at
                notification.save(update_fields=['status', 'attempt_count', 'last_attempt_at', 'updated_at'])

    def _render_subject(self, template: Optional[EmailTemplate], context: dict) -> str:
        if template and template.subject_template:
            return Template(template.subject_template).render(Context(context)).strip()
        return context.get('title') or 'New update from Vetri Training'

    def _render_body(self, template: Optional[EmailTemplate], context: dict) -> str:
        if template and template.body_template:
            return Template(template.body_template).render(Context(context))
        return render_to_string('emails/default_notification.txt', context)

    def _from_email(self) -> str:
        default = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if default:
            return default
        return 'no-reply@vtstraining.local'

    def _get_template(self, slug: str) -> Optional[EmailTemplate]:
        try:
            return EmailTemplate.objects.get(slug=slug)
        except EmailTemplate.DoesNotExist:
            logger.warning("Email template '%s' is missing", slug)
            return None

    def _get_preferences(self, trainee: Trainee) -> NotificationPreference:
        pref, _ = NotificationPreference.objects.get_or_create(trainee=trainee)
        return pref

    def _should_notify(self, pref: NotificationPreference, field: str) -> bool:
        return getattr(pref, field, True)

    def _normalize_timestamp(self, value) -> datetime:
        if isinstance(value, datetime):
            aware = value if timezone.is_aware(value) else timezone.make_aware(value)
            return timezone.localtime(aware)
        if isinstance(value, date):
            naive = datetime.combine(value, time.min)
            aware = timezone.make_aware(naive)
            return timezone.localtime(aware)
        return timezone.localtime(timezone.now())

    def _format_timestamp(self, dt: datetime) -> str:
        return dt.strftime('%d %b %Y %I:%M %p %Z')
