from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

from .models import Teacher, Venue, Assignment

last_assignment_ids = set()

def assign_teachers_randomly():
    global last_assignment_ids

    clean_expired_assignments()  # Remove expired assignments first

    new_internal_teachers = list(Teacher.objects.filter(is_temporary=False).exclude(teacher_id__in=last_assignment_ids).order_by('?'))
    new_external_teachers = list(Teacher.objects.filter(is_temporary=True).order_by('?'))
    all_new_teachers = new_external_teachers + new_internal_teachers

    previous_teachers = list(Teacher.objects.filter(teacher_id__in=last_assignment_ids).order_by('?'))
    all_teachers = all_new_teachers + previous_teachers

    venues = Venue.objects.filter(required=True)

    if not all_teachers or not venues:
        print("No teachers or venues available. No assignments created.")
        return

    with transaction.atomic():
        Assignment.objects.all().delete()
        last_assignment_ids.clear()

        for venue in venues:
            selected_teachers = all_teachers[:venue.staff_count]

            for teacher in selected_teachers:
                Assignment.objects.create(
                    teacher=teacher,
                    venue=venue,
                    attendance_status="Absent"
                )
                last_assignment_ids.add(teacher.teacher_id)

            all_teachers = all_teachers[venue.staff_count:]






def clean_expired_assignments():
    expired_assignments = Assignment.objects.filter(assigned_at__lt=now() - timedelta(hours=1))
    if expired_assignments.exists():
        expired_assignments.delete()

