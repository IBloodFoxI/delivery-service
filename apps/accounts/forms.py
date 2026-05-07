from django import forms
from django.contrib.auth import authenticate
from .models import User


class RegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=255,
        label='ФИО',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иванов Иван Иванович'}),
    )
    phone_number = forms.CharField(
        max_length=20,
        label='Номер телефона',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@mail.ru'}),
    )
    password = forms.CharField(
        label='Пароль',
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Минимум 6 символов'}),
    )
    password_confirm = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Повторите пароль'}),
    )

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) < 10:
            raise forms.ValidationError('Введите корректный номер телефона')
        from .crypto import make_hash
        if User.objects.filter(phone_hash=make_hash(phone)).exists():
            raise forms.ValidationError('Пользователь с таким номером уже зарегистрирован')
        return phone

    def clean_email(self):
        from .crypto import make_hash
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email_hash=make_hash(email)).exists():
            raise forms.ValidationError('Пользователь с таким email уже зарегистрирован')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Пароли не совпадают')
        return cleaned


class LoginForm(forms.Form):
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
        label='Номер телефона'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'}),
        label='Пароль'
    )

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get('phone_number')
        password = cleaned.get('password')
        if phone and password:
            user = authenticate(phone_number=phone, password=password)
            if user is None:
                raise forms.ValidationError('Неверный номер телефона или пароль')
            if not user.is_active:
                raise forms.ValidationError('Аккаунт заблокирован')
            cleaned['user'] = user
        return cleaned


class TopUpForm(forms.Form):
    AMOUNT_CHOICES = [
        (100, '100 ₽'),
        (300, '300 ₽'),
        (500, '500 ₽'),
        (1000, '1 000 ₽'),
        (2000, '2 000 ₽'),
        (5000, '5 000 ₽'),
    ]
    amount = forms.ChoiceField(
        choices=AMOUNT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'amount-radio'}),
        label='Сумма пополнения'
    )
    custom_amount = forms.DecimalField(
        required=False,
        min_value=10,
        max_value=100000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Другая сумма'}),
        label='Другая сумма'
    )

    def clean(self):
        cleaned = super().clean()
        custom = cleaned.get('custom_amount')
        if custom:
            cleaned['final_amount'] = custom
        else:
            cleaned['final_amount'] = int(cleaned.get('amount', 0))
        return cleaned


class ProfileEditForm(forms.ModelForm):
    # Отдельное поле — показывает расшифрованный номер, сохраняет зашифрованным
    phone_plain = forms.CharField(
        label='Номер телефона',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ['full_name', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['phone_plain'].initial = self.instance.phone_display

    def clean_phone_plain(self):
        from .crypto import make_hash
        phone = self.cleaned_data.get('phone_plain', '').strip()
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) < 10:
            raise forms.ValidationError('Введите корректный номер телефона')
        # Проверяем уникальность — исключаем самого себя
        qs = User.objects.filter(phone_hash=make_hash(phone))
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Этот номер уже занят')
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        phone = self.cleaned_data.get('phone_plain', '').strip()
        if phone:
            user.set_phone(phone)
        if commit:
            user.save()
        return user
