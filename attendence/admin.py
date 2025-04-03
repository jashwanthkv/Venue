from django.contrib import admin
from .models import Teacher, Venue, Assignment



class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'required', 'staff_count']
    list_editable = ['required', 'staff_count']


class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'venue', 'attendance_status', 'assigned_at']
    list_filter = ['venue', 'attendance_status']
    readonly_fields = ['assigned_at']
    actions = ['reset_assignments']

    # def reset_assignments(self, request, queryset):
    #     reset_assignments()
    #     self.message_user(request, "Assignments reset and new teachers assigned!")
    #
    # reset_assignments.short_description = "Reset and reassign teachers"


admin.site.register(Teacher)
admin.site.register(Venue, VenueAdmin)
admin.site.register(Assignment, AssignmentAdmin)

