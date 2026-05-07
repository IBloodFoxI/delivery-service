from django import forms


class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'г. Москва, ул. Примерная, д. 1, кв. 1'
        }),
        label='Адрес доставки'
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Комментарий для курьера (необязательно)'
        }),
        label='Комментарий курьеру'
    )
