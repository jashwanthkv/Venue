from datetime import timedelta
from django.forms import modelformset_factory
from django.db import transaction
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import now
from .models import Venue, Teacher, Assignment
from .forms import VenueSelectionForm, Form_to_data, ExternalTeacherForm
from .utils import assign_teachers_randomly
import pandas as pd

show_assignments = False

def home_page(request):
    global show_assignments
    clean_expired_assignments()

    assignments = Assignment.objects.select_related('teacher', 'venue').all()
    external_teachers = Teacher.objects.filter(is_temporary=True)

    for teacher in external_teachers:
        if teacher.is_expired():
            teacher.delete()

    if request.method == 'POST':
        if 'save_attendance' in request.POST:
            for assignment in assignments:
                checkbox_name = f'attendance_{assignment.id}'
                assignment.attendance_status = "Present" if checkbox_name in request.POST else "Absent"
                assignment.save()
            return redirect('home_page')

        if 'generate_list' in request.POST:
            show_assignments = True
            assign_teachers_randomly()

    valid_assignments = [assignment for assignment in assignments if not assignment.is_expired()]

    return render(request, "home.html", {
        'assignments': valid_assignments if show_assignments else [],
        'show_assignments': show_assignments and bool(valid_assignments)
    })


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
    expired_assignments = Assignment.objects.filter(assigned_at__lt=now() - timedelta(minutes=180))
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

def scan_qr(request, venue_id):
    if request.method == "POST":
        teacher_id = request.POST["teacher_id"]
        email = request.POST["email"]

        teacher = Teacher.objects.filter(teacher_id=teacher_id, email=email).first()
        if not teacher:
            return render(request, "scan.html", {"error": "Invalid Teacher ID or Email"})

        # Generate OTP and save in DB
        otp = random.randint(100000, 999999)
        OTPRecord.objects.update_or_create(email=email, defaults={"otp": otp, "created_at": now()})

        # Send OTP via Email
        send_mail("Your OTP for Attendance", f"Your OTP is {otp}.", "noreply@yourdomain.com", [email])

        request.session["teacher_email"] = email
        request.session["venue_id"] = venue_id
        return redirect("verify_otp")

    return render(request, "scan.html", {"venue_id": venue_id})


def verify_otp(request):
    if request.method == "POST":
        email = request.session.get("teacher_email")
        venue_id = request.session.get("venue_id")
        entered_otp = request.POST["otp"]

        otp_record = OTPRecord.objects.filter(email=email).first()

        if otp_record and otp_record.otp == int(entered_otp) and otp_record.is_valid():
            teacher = Teacher.objects.get(email=email)
            assignment = Assignment.objects.filter(teacher=teacher, venue_id=venue_id).first()

            if assignment:
                assignment.attendance_status = "Present"
                assignment.save()
                otp_record.delete()  # Remove OTP after use
                return render(request, "confirmation.html", {"message": "Attendance Marked Successfully!"})
            else:
                return render(request, "confirmation.html", {"message": "No assignment found for this venue!"})

        return render(request, "otp_verification.html", {"error": "Incorrect or Expired OTP"})

    return render(request, "otp_verification.html")

def save_attendance(request):
    if request.method == "POST":
        email = request.session.get("teacher_email")
        venue_id = request.session.get("venue_id")

        teacher = Teacher.objects.filter(email=email).first()
        if teacher:
            assignment = Assignment.objects.filter(teacher=teacher, venue_id=venue_id).first()
            if assignment:
                assignment.attendance_status = "Present"
                assignment.save()
                return JsonResponse({"success": True})

    return JsonResponse({"success": False})
