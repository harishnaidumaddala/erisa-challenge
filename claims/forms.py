from django import forms
from .models import Note

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['kind', 'body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add note...'}),
        }

class CsvUploadForm(forms.Form):
    list_file = forms.FileField(required=True, help_text="Pipe '|' delimited list CSV")
    detail_file = forms.FileField(required=False, help_text="Pipe '|' delimited detail CSV")
    MODE_CHOICES = [("append", "Append"), ("overwrite", "Overwrite existing data")]
    mode = forms.ChoiceField(choices=MODE_CHOICES, initial="append")
