from django import forms
from .models import ComplianceItem, ComplianceComment

class ComplianceMarkDoneForm(forms.ModelForm):
    class Meta:
        model = ComplianceItem
        fields = ['reference_number', 'remarks', 'document_link']
        widgets = {
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Challan # / Ack # / Ref Code'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional completion notes or remarks...'}),
            'document_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }

class ComplianceCommentForm(forms.ModelForm):
    class Meta:
        model = ComplianceComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write boss comment for this compliance item...'}),
        }
