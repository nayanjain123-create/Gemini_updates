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

class TaskReallocationForm(forms.Form):
    reallocate_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True, role=User.EMPLOYEE).order_by('full_name', 'username'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Delegate / Transfer Task To"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'State the clear reason why you are re-allocating this task (e.g. Busy with returns, assigned to another priority container)...'
        }),
        label="Reason for Reallocation",
        required=True
    )

class TaskRemarkForm(forms.Form):
    remark = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Provide feedback or specify what is incomplete before approving this task...'
        }),
        label="Boss Remark / Revision Instructions",
        required=True
    )

