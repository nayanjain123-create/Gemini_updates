from django import forms
from accounts.models import User
from .models import DailyTaskReport, DailyTaskComment, AssignedTask

class DailyTaskForm(forms.ModelForm):
    class Meta:
        model = DailyTaskReport
        fields = ['task_description']
        widgets = {
            'task_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe your daily work tasks...'}),
        }

class DailyTaskCommentForm(forms.ModelForm):
    class Meta:
        model = DailyTaskComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write a comment for this daily task entry...'}),
        }

class AssignedTaskForm(forms.ModelForm):
    class Meta:
        model = AssignedTask
        fields = ['title', 'description', 'assigned_to', 'priority', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task title...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Task instructions or details...'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit assigned_to choices to active employees
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('full_name', 'username')

class AssignedTaskStatusForm(forms.ModelForm):
    class Meta:
        model = AssignedTask
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
