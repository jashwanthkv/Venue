import base64
from datetime import timedelta
from io import BytesIO

import qrcode
from django.forms import modelformset_factory
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from .models import Venue, Teacher, Assignment
from .forms import VenueSelectionForm, Form_to_data, ExternalTeacherForm
from .utils import assign_teachers_randomly
import pandas as pd

show_assignments = False
def home_page(request):
    clean_expired_assignments()

    assignments = Assignment.objects.select_related('teacher', 'venue').all()
    valid_assignments = [a for a in assignments if not a.is_expired()]

    external_teachers = Teacher.objects.filter(is_temporary=True)
    for teacher in external_teachers:
        if teacher.is_expired():
            teacher.delete()

    # ✅ Save attendance manually
    if request.method == 'POST' and 'save_attendance' in request.POST:
        for assignment in assignments:
            checkbox_name = f'attendance_{assignment.id}'
            assignment.attendance_status = "Present" if checkbox_name in request.POST else "Absent"
            assignment.save()
        return redirect('home_page')

    # ✅ Generate new assignment list
    if request.method == 'POST' and 'generate_list' in request.POST:
        with transaction.atomic():
            clean_expired_assignments()
            Assignment.objects.all().delete()
            assign_teachers_randomly()
        return redirect('home_page')

    return render(request, "home.html", {
        'assignments': valid_assignments,
        'show_assignments': bool(valid_assignments)
    })

def assignment_data(request):
    assignments = Assignment.objects.select_related('teacher', 'venue').all()
    data = []

    for assignment in assignments:
        data.append({
            'teacher_id': assignment.teacher.teacher_id,
            'name': assignment.teacher.name,
            'department': assignment.teacher.department,
            'venue': assignment.venue.name,
            'status': assignment.attendance_status,
        })

    return JsonResponse({'assignments': data})


def generate_assignments(request):
    with transaction.atomic():
        clean_expired_assignments()
        Assignment.objects.all().delete()
        assign_teachers_randomly()
    return redirect('home_page')


def add_external_teacher(request):
    if request.method == 'POST':
        form = ExternalTeacherForm(request.POST)
        if form.is_valid():
            external_teacher = form.save(commit=False)
            external_teacher.is_temporary = True
            external_teacher.save()
            return redirect('home_page')
    else:
        form = ExternalTeacherForm()
    return render(request, "add_external_teacher.html", {'form': form})


def clean_expired_assignments():
    expired_assignments = Assignment.objects.filter(assigned_at__lt=now() - timedelta(minutes=20))
    if expired_assignments.exists():
        expired_assignments.delete()


def random_assignment(request):
    with transaction.atomic():
        clean_expired_assignments()
        Assignment.objects.all().delete()
        assign_teachers_randomly()
    return redirect('home_page')


def download_attendance(request):
    assignments = Assignment.objects.select_related('teacher', 'venue').all()
    data = [[
        assignment.teacher.teacher_id,
        assignment.teacher.name,
        assignment.teacher.department,
        assignment.venue.name,
        assignment.attendance_status,
    ] for assignment in assignments]

    df = pd.DataFrame(data, columns=["Teacher ID", "Name", "Department", "Venue", "Attendance"])

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="attendance_list.xlsx"'
    df.to_excel(response, index=False)

    return response


def venue_selection_view(request):
    VenueFormSet = modelformset_factory(Venue, form=VenueSelectionForm, extra=0)
    queryset = Venue.objects.all()

    if request.method == 'POST':
        formset = VenueFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            for form in formset:
                venue = form.instance
                print(f"Updated venue: {venue.name}, Required: {venue.required}, Staff Count: {venue.staff_count}")
            return redirect('venue-selection')

    else:
        formset = VenueFormSet(queryset=queryset)

    return render(request, 'venue_selection.html', {'formset': formset})


def assignment_list(request):
    venue_filter = request.GET.get('venue')
    status_filter = request.GET.get('status')

    assignments = Assignment.objects.select_related('teacher', 'venue')

    if venue_filter and venue_filter != "All":
        assignments = assignments.filter(venue__name=venue_filter)

    if status_filter and status_filter != "All":
        assignments = assignments.filter(attendance_status=status_filter)

    venues = Venue.objects.all()
    attendance_counts = {
        "Present": assignments.filter(attendance_status="Present").count(),
        "Absent": assignments.filter(attendance_status="Absent").count(),
        "All": assignments.count(),
    }

    return render(request, 'assignment_list.html', {
        'assignments': assignments,
        'venues': venues,
        'attendance_counts': attendance_counts,
        'selected_venue': venue_filter,
        'selected_status': status_filter,
    })


def download_template(request):
    data = {"id": [], "name": [], "dept": [], "gender": [], "ph": [], "email": []}  # Added email column
    df = pd.DataFrame(data)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=teacher_template.xlsx'
    df.to_excel(response, index=False)
    return response


def upload_teachers(request):
    if request.method == 'POST':
        form = Form_to_data(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']
            try:
                df = pd.read_excel(excel_file)
                for _, row in df.iterrows():
                    Teacher.objects.get_or_create(
                        teacher_id=row['id'],
                        name=row['name'],
                        department=row['dept'],
                        gender=row['gender'],
                        phone_number=row['ph'],
                        email=row['email']  # Ensure email is saved
                    )
                return redirect('upload_teachers')
            except Exception as e:
                return render(request, 'upload.html', {'form': form, 'error': str(e)})
    else:
        form = Form_to_data()
    return render(request, 'upload.html', {'form': form})





from django.core.mail import send_mail
import random

OTP_STORE = {}

from .models import OTPRecord


@csrf_exempt
def scan_qr(request, venue_id):
    if request.method == "POST":
        teacher_id = request.POST["teacher_id"]
        email = request.POST["email"]

        # Check if a teacher exists with this ID and email
        teacher = Teacher.objects.filter(teacher_id=teacher_id, email=email).first()
        if not teacher:
            return render(request, "scan.html", {
                "error": "Invalid Teacher ID or Email",
                "venue_id": venue_id
            })

        # Generate OTP and save in DB
        otp = random.randint(100000, 999999)
        OTPRecord.objects.update_or_create(email=email, defaults={
            "otp": otp,
            "created_at": now()
        })

        # Send OTP via Email
        send_mail(
            "Your OTP for Attendance",
            f"Your OTP is {otp}.",
            "jashwanthkv2005@gmail.com",  # Replace with DEFAULT_FROM_EMAIL or actual email
            [email]
        )

        # Store necessary session data
        request.session["teacher_email"] = email
        request.session["teacher_id"] = teacher_id
        request.session["venue_id"] = venue_id

        return redirect("verify_otp")

    return render(request, "scan.html", {"venue_id": venue_id})

@csrf_exempt
def verify_otp(request):
    if request.method == "POST":
        email = request.session.get("teacher_email")
        teacher_id = request.session.get("teacher_id")
        venue_id = request.session.get("venue_id")
        entered_otp = request.POST["otp"]

        otp_record = OTPRecord.objects.filter(email=email).first()

        if otp_record and otp_record.otp == int(entered_otp) and otp_record.is_valid():
            teacher = Teacher.objects.filter(email=email, teacher_id=teacher_id).first()

            if not teacher:
                return render(request, "otp_verification.html", {
                    "error": "Teacher not found with given email and ID."
                })

            assignment = Assignment.objects.filter(teacher=teacher, venue_id=venue_id).first()

            if assignment:
                assignment.attendance_status = "Present"
                assignment.save()
                otp_record.delete()  # Remove OTP after use
                return render(request, "confirmation.html", {"message": "Attendance Marked Successfully!"})
            else:
                return render(request, "confirmation.html", {"message": "No assignment found for this venue!"})

        return render(request, "otp_verification.html", {
            "error": "Incorrect or Expired OTP"
        })

    return render(request, "otp_verification.html")

@csrf_exempt
def save_attendance(request):
    if request.method == "POST":
        email = request.session.get("teacher_email")
        teacher_id = request.session.get("teacher_id")
        venue_id = request.session.get("venue_id")

        teacher = Teacher.objects.filter(email=email, teacher_id=teacher_id).first()
        if teacher:
            assignment = Assignment.objects.filter(teacher=teacher, venue_id=venue_id).first()
            if assignment:
                assignment.attendance_status = "Present"
                assignment.save()
                return JsonResponse({"success": True})

    return JsonResponse({"success": False})


# from .models import Venue
#
# def generate_all_qr_codes(request):
#     venues = Venue.objects.all()  # Or filter if needed
#     qr_codes = []
#
#     for venue in venues:
#         venue_id = venue.id  # or venue.code or venue.name, based on your model
#         url = f"http://127.0.0.1:8000/scan/{venue_id}"
#         qr = qrcode.make(url)
#         buffer = BytesIO()
#         qr.save(buffer, format="PNG")
#         img_base64 = base64.b64encode(buffer.getvalue()).decode()
#         qr_codes.append({"id": venue_id, "img": img_base64})
#
#     return render(request, "qr_codes.html", {"qr_codes": qr_codes})
