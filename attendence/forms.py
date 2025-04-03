from django import forms
from .models import Venue
from .models import Assignment

class VenueSelectionForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ['name', 'required', 'staff_count']
        widgets = {
            'name': forms.TextInput(attrs={'readonly': 'readonly'}),  # Prevent name changes
            'required': forms.CheckboxInput(),
            'staff_count': forms.NumberInput(attrs={'min': 1}),
        }
from django import forms
from .models import Teacher

class ExternalTeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['name', 'department', 'gender', 'phone_number','email']

    def save(self, commit=True):
        teacher = super().save(commit=False)
        teacher.is_temporary = True
        if commit:
            teacher.save()
        return teacher

from django import forms


class Form_to_data(forms.Form):
    file = forms.FileField(label="Upload your file")


class ManualAssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['teacher', 'venue', 'attendance_status']


