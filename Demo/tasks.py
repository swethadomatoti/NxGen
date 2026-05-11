import logging

import pytz
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import DemoSchedule

logger = logging.getLogger(__name__)


def _get_ist_scheduled_time(demo_schedule):
    return demo_schedule.scheduled_at



def _build_lead_email_body(demo_schedule, lead):
    scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
    return f"""
Hi {lead.fullname},
We are pleased to inform you that your demo session has been successfully scheduled.
Course : {demo_schedule.campaign.name}

Details:
Date: {scheduled_at_ist.date()}
Time: {scheduled_at_ist.time()}
Instructor: {demo_schedule.instructor.full_name}
Meeting link: {demo_schedule.meeting_link}

Please join the meeting on time.

Regards,
Team Nxgen
"""


def _build_instructor_email_body(demo_schedule, total_leads):
    scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
    return f"""
Hello {demo_schedule.instructor.full_name},

Course : {demo_schedule.campaign.name}

Details:
Date: {scheduled_at_ist.date()}
Time: {scheduled_at_ist.time()}
Meeting link: {demo_schedule.meeting_link}
Total interested leads: {total_leads}

Please review the leads and join on time.

Regards,
Team Nxgen
"""


def _build_lead_reschedule_email_body(demo_schedule, lead, original_demo=None):
    scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
    original_details = ""
    if original_demo is not None:
        original_at = _get_ist_scheduled_time(original_demo)
        original_details = f"\nPrevious Demo:\nDate: {original_at.date()}\nTime: {original_at.time()}\nMeeting link: {original_demo.meeting_link}\n"

    return f"""
Hi {lead.fullname},

Your demo has been rescheduled for:
Course : {demo_schedule.campaign.name}

Details:
Date: {scheduled_at_ist.date()}
Time: {scheduled_at_ist.time()}
Instructor: {demo_schedule.instructor.full_name}
Meeting link: {demo_schedule.meeting_link}
{original_details}
Please join the meeting on time.

Regards,
Team Nxgen
"""


def _build_instructor_reschedule_email_body(demo_schedule, total_leads, original_demo=None):
    scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
    original_details = ""
    if original_demo is not None:
        original_at = _get_ist_scheduled_time(original_demo)
        original_details = f"\nPrevious Demo:\nDate: {original_at.date()}\nTime: {original_at.time()}\nMeeting link: {original_demo.meeting_link}\n"

    return f"""
Hello {demo_schedule.instructor.full_name},

A demo has been rescheduled for:
Course : {demo_schedule.campaign.name}

Details:
Date: {scheduled_at_ist.date()}
Time: {scheduled_at_ist.time()}
Meeting link: {demo_schedule.meeting_link}
Total interested leads: {total_leads}
{original_details}
Please review the leads and join on time.

Regards,
Team Nxgen
"""


def send_demo_schedule_emails(demo_schedule_id):
    demo_schedule = (
        DemoSchedule.objects
        .select_related('campaign', 'instructor')
        .prefetch_related('leads')
        .filter(pk=demo_schedule_id)
        .first()
    )

    if demo_schedule is None:
        logger.error("DemoSchedule not found for email send: %s", demo_schedule_id)
        return False

    for lead in demo_schedule.leads.all():
        scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
        subject = f"Demo Scheduled for {demo_schedule.campaign.name}"
        text_body = _build_lead_email_body(demo_schedule, lead)
        html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e6e6e6; border-radius: 8px; background: #f9fafb;">
      <h2 style="color: #1a73e8;">Demo Scheduled</h2>
      <p>Hi {lead.fullname},</p>
      <p>Course : <strong>{demo_schedule.campaign.name}</strong></p>
      <div style="background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 16px;">
        <p style="margin: 0 0 10px 0; font-weight: 600;">Details</p>
        <div style="margin: 10px 0 0 0; color: #4b5563; line-height: 1.6;">
          <p style="margin: 0 0 8px 0;">Date: {scheduled_at_ist.date()}</p>
          <p style="margin: 0 0 8px 0;">Time: {scheduled_at_ist.time()}</p>
          <p style="margin: 0 0 8px 0;">Instructor: {demo_schedule.instructor.full_name}</p>
          <p style="margin: 0;">Meeting link: <a href="{demo_schedule.meeting_link}" style="color: #1a73e8; text-decoration: none;">Join demo</a></p>
        </div>
      </div>
      <p style="margin-top: 16px;">Please join the meeting on time.</p>
      <p>Regards,<br>Team Nxgen</p>
    </div>
  </body>
</html>
"""
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_HOST_USER,
            to=[lead.email],
        )
        message.attach_alternative(html_body, "text/html")
        try:
            message.send(fail_silently=False)
        except Exception as exc:
            logger.exception(
                "Failed to send demo email to lead %s for DemoSchedule %s: %s",
                lead.email,
                demo_schedule.id,
                exc,
            )

    scheduled_at_ist = _get_ist_scheduled_time(demo_schedule)
    subject = f"Demo Assigned: {demo_schedule.campaign.name}"
    text_body = _build_instructor_email_body(demo_schedule, demo_schedule.leads.count())
    html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e6e6e6; border-radius: 8px; background: #f9fafb;">
      <h2 style="color: #1a73e8;">Demo Assigned</h2>
      <p>Hello {demo_schedule.instructor.full_name},</p>
      <p>Course : <strong>{demo_schedule.campaign.name}</strong></p>
      <div style="background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 16px;">
        <p style="margin: 0 0 10px 0; font-weight: 600;">Details</p>
        <div style="margin: 10px 0 0 0; color: #4b5563; line-height: 1.6;">
          <p style="margin: 0 0 8px 0;">Date: {scheduled_at_ist.date()}</p>
          <p style="margin: 0 0 8px 0;">Time: {scheduled_at_ist.time()}</p>
          <p style="margin: 0 0 8px 0;">Meeting link: <a href="{demo_schedule.meeting_link}" style="color: #1a73e8; text-decoration: none;">Join demo</a></p>
          <p style="margin: 0;">Total interested leads: {demo_schedule.leads.count()}</p>
        </div>
      </div>
      <p style="margin-top: 16px;">Please review the leads and join on time.</p>
      <p>Regards,<br>Team Nxgen</p>
    </div>
  </body>
</html>
"""
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.EMAIL_HOST_USER,
        to=[demo_schedule.instructor.email],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception(
            "Failed to send demo notification email to instructor %s for DemoSchedule %s: %s",
            demo_schedule.instructor.email,
            demo_schedule.id,
            exc,
        )

    logger.info(
        "Completed DemoSchedule email send %s: lead_count=%s instructor=%s",
        demo_schedule.id,
        demo_schedule.leads.count(),
        demo_schedule.instructor.email,
    )
    return True


def send_demo_reschedule_emails(demo_schedule_id, original_demo_id=None):
    demo_schedule = (
        DemoSchedule.objects
        .select_related('campaign', 'instructor')
        .prefetch_related('leads')
        .filter(pk=demo_schedule_id)
        .first()
    )

    if demo_schedule is None:
        logger.error("DemoSchedule not found for reschedule email send: %s", demo_schedule_id)
        return False

    original_demo = None
    if original_demo_id is not None:
        original_demo = DemoSchedule.objects.filter(pk=original_demo_id).first()

    for lead in demo_schedule.leads.all():
        subject = f"Demo Rescheduled for {demo_schedule.campaign.name}"
        text_body = _build_lead_reschedule_email_body(demo_schedule, lead, original_demo)
        html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e6e6e6; border-radius: 8px; background: #f9fafb;">
      <h2 style="color: #1a73e8;">Demo Rescheduled</h2>
      <p>Hi {lead.fullname},</p>
      <p>We would like to inform you that your demo session has been rescheduled.</p>
      <p>Course : <strong>{  demo_schedule.campaign.name}</strong></p>
      <div style="background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 16px;">
        <p style="margin: 0 0 10px 0; font-weight: 600;">Details</p>
        <div style="margin: 10px 0 0 0; color: #4b5563; line-height: 1.6;">
          <p style="margin: 0 0 8px 0;">Date: { _get_ist_scheduled_time(demo_schedule).date() }</p>
          <p style="margin: 0 0 8px 0;">Time: { _get_ist_scheduled_time(demo_schedule).time() }</p>
          <p style="margin: 0 0 8px 0;">Instructor: {demo_schedule.instructor.full_name}</p>
          <p style="margin: 0;">Meeting link: <a href="{demo_schedule.meeting_link}" style="color: #1a73e8; text-decoration: none;">Join demo</a></p>
        </div>
      </div>
      <p style="margin-top: 16px;">Please join the meeting on time.</p>
      <p>Regards,<br>Team Nxgen</p>
    </div>
  </body>
</html>
"""
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_HOST_USER,
            to=[lead.email],
        )
        message.attach_alternative(html_body, "text/html")
        try:
            message.send(fail_silently=False)
        except Exception as exc:
            logger.exception(
                "Failed to send demo reschedule email to lead %s for DemoSchedule %s: %s",
                lead.email,
                demo_schedule.id,
                exc,
            )

    subject = f"Demo Rescheduled: {demo_schedule.campaign.name}"
    text_body = _build_instructor_reschedule_email_body(demo_schedule, demo_schedule.leads.count(), original_demo)
    html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e6e6e6; border-radius: 8px; background: #f9fafb;">
      <h2 style="color: #1a73e8;">Demo Rescheduled</h2>
      <p>Hello {demo_schedule.instructor.full_name},</p>
      <p>Course : <strong>{demo_schedule.campaign.name}</strong></p>
      <div style="background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 16px;">
        <p style="margin: 0 0 10px 0; font-weight: 600;">Details</p>
        <div style="margin: 10px 0 0 0; color: #4b5563; line-height: 1.6;">
          <p style="margin: 0 0 8px 0;">Date: { _get_ist_scheduled_time(demo_schedule).date() }</p>
          <p style="margin: 0 0 8px 0;">Time: { _get_ist_scheduled_time(demo_schedule).time() }</p>
          <p style="margin: 0 0 8px 0;">Meeting link: <a href="{demo_schedule.meeting_link}" style="color: #1a73e8; text-decoration: none;">Join demo</a></p>
          <p style="margin: 0;">Total interested leads: {demo_schedule.leads.count()}</p>
        </div>
      </div>
      <p style="margin-top: 16px;">Please review the leads and join on time.</p>
      <p>Regards,<br>Team Nxgen</p>
    </div>
  </body>
</html>
"""
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.EMAIL_HOST_USER,
        to=[demo_schedule.instructor.email],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        logger.exception(
            "Failed to send demo reschedule notification email to instructor %s for DemoSchedule %s: %s",
            demo_schedule.instructor.email,
            demo_schedule.id,
            exc,
        )

    logger.info(
        "Completed DemoSchedule reschedule email send %s: lead_count=%s instructor=%s",
        demo_schedule.id,
        demo_schedule.leads.count(),
        demo_schedule.instructor.email,
    )
    return True
