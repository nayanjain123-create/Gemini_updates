from django import forms
from .models import ComplianceItem, ComplianceComment

class ComplianceMarkDoneForm(forms.ModelForm):
    class Meta:
        model = ComplianceItem
        fields = ['remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional completion notes or remarks...'}),
        }

class ComplianceCommentForm(forms.ModelForm):
    class Meta:
        model = ComplianceComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write boss comment for this compliance item...'}),
        }
