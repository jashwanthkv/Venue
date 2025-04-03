from django.db import models
from django.utils.timezone import now, timedelta
import uuid

class Teacher(models.Model):
    teacher_id = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female')],
        default='Male'
    )
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(unique=False)  # Added email field
    is_temporary = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        tag = "External" if self.is_temporary else "Internal"
        return f"{self.name} - {self.department} ({tag})"

    def save(self, *args, **kwargs):
        if not self.teacher_id:
            self.teacher_id = f"EXT-{uuid.uuid4().hex[:6]}" if self.is_temporary else f"INT-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    def is_expired(self):
        assignment = Assignment.objects.filter(teacher=self).order_by('-assigned_at').first()
        if assignment and now() > assignment.assigned_at + timedelta(minutes=5):
            return True
        return False


class Venue(models.Model):
    name = models.CharField(max_length=100)
    required = models.BooleanField(default=False)
    staff_count = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name


class Assignment(models.Model):
    id = models.AutoField(primary_key=True)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE)
    venue = models.ForeignKey('Venue', on_delete=models.CASCADE)
    attendance_status = models.CharField(
        max_length=10,
        choices=[('Present', 'Present'), ('Absent', 'Absent')],
        default='Absent'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'venue')

    def is_expired(self):
        return now() > self.assigned_at + timedelta(hours=5)


from django.db import models
from django.utils.timezone import now

class OTPRecord(models.Model):
    email = models.EmailField(unique=True)
    otp = models.IntegerField()
    created_at = models.DateTimeField(default=now)

    def is_valid(self):
        return (now() - self.created_at).seconds < 300


def create_default_venues():
    default_venues = ['Hall A', 'Hall B', 'Hall C', 'Lab 1', 'Lab 2',
                      'Auditorium', 'Seminar Room', 'Conference Room',
                      'Library', 'Sports Complex']
    for venue in default_venues:
        Venue.objects.get_or_create(name=venue)
