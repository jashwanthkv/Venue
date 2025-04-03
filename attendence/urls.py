from django.urls import path
from . import views
from django.contrib import admin

urlpatterns = [
    path('', views.home_page, name='home_page'),
    path('admin/', admin.site.urls),
    path('download_template/', views.download_template, name='download_template'),
    path('venues/', views.venue_selection_view, name='venue-selection'),
    path('uploads/', views.upload_teachers, name="upload_teachers"),
    path('assign/', views.assignment_list, name="assignment_list"),
    path('random-assignment/', views.random_assignment, name='random_assignment'),
    path('download-attendance/', views.download_attendance, name='download_attendance'),
    path('add-external/', views.add_external_teacher, name='add_external_teacher'),
    path("scan/<int:venue_id>/", views.scan_qr, name="scan_qr"),
    path("verify_otp/", views.verify_otp, name="verify_otp"),
    path("save_attendance/", views.save_attendance, name="save_attendance"),

]
