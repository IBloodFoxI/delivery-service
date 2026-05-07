from django import forms
from .models import SupportTicket, TicketMessage


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Опишите проблему кратко'}),
        }

    first_message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Подробное описание проблемы'}),
        label='Сообщение'
    )


class TicketReplyForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ваше сообщение...'}),
        label='Сообщение'
    )
