from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.conf import settings
from .forms import RegisterForm, LoginForm, TopUpForm, ProfileEditForm
from .models import User, BalanceTransaction


def _send_verification_code(email, code):
    from .email_utils import send_email
    send_email(
        to=email,
        subject='Код подтверждения — Доставка МИГ',
        text=(
            f'Ваш код подтверждения для регистрации: {code}\n\n'
            f'Код действует 10 минут.\n'
            f'Если вы не регистрировались — проигнорируйте это письмо.'
        ),
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            import random, time
            from django.contrib.auth.hashers import make_password
            data = form.cleaned_data
            code = str(random.randint(100000, 999999))
            request.session['pending_reg'] = {
                'full_name': data['full_name'],
                'phone_number': data['phone_number'],
                'email': data['email'],
                'password_hash': make_password(data['password']),
            }
            request.session['email_code'] = code
            request.session['email_code_expires'] = time.time() + 600
            try:
                _send_verification_code(data['email'], code)
                messages.info(request, f'Код подтверждения отправлен на {data["email"]}')
            except Exception:
                messages.warning(request, f'Код подтверждения (email не отправлен): {code}')
            return redirect('accounts:verify_email')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def verify_email_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    pending = request.session.get('pending_reg')
    if not pending:
        messages.error(request, 'Сессия регистрации истекла. Начните заново.')
        return redirect('accounts:register')

    if request.method == 'POST':
        import time
        entered = request.POST.get('code', '').strip()
        stored_code = request.session.get('email_code', '')
        expires = request.session.get('email_code_expires', 0)

        if time.time() > expires:
            messages.error(request, 'Код истёк. Зарегистрируйтесь заново.')
            for k in ('pending_reg', 'email_code', 'email_code_expires'):
                request.session.pop(k, None)
            return redirect('accounts:register')

        if entered != stored_code:
            messages.error(request, 'Неверный код. Проверьте почту и попробуйте снова.')
            return render(request, 'accounts/verify_email.html', {'email': pending['email']})

        user = User(full_name=pending['full_name'])
        user.set_phone(pending['phone_number'])
        user.set_email_encrypted(pending['email'])
        user.password = pending['password_hash']
        user.save()
        for k in ('pending_reg', 'email_code', 'email_code_expires'):
            request.session.pop(k, None)
        login(request, user)
        messages.success(request, f'Добро пожаловать, {user.full_name}! Регистрация завершена.')
        return redirect('home')

    if request.GET.get('resend') == '1':
        import random, time
        code = str(random.randint(100000, 999999))
        request.session['email_code'] = code
        request.session['email_code_expires'] = time.time() + 600
        try:
            _send_verification_code(pending['email'], code)
            messages.info(request, 'Новый код отправлен на вашу почту.')
        except Exception as e:
            messages.error(request, f'Ошибка отправки: {e}')
        return redirect('accounts:verify_email')

    return render(request, 'accounts/verify_email.html', {'email': pending['email']})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            next_url = request.GET.get('next', '')
            if next_url:
                return redirect(next_url)
            if user.is_courier:
                return redirect('courier:dashboard')
            elif user.is_support:
                return redirect('support_panel:dashboard')
            elif user.is_admin_role or user.is_staff:
                return redirect('admin_panel:dashboard')
            return redirect('home')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён')
            return redirect('accounts:profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def topup_view(request):
    if request.user.is_customer:
        messages.error(request, 'Пополнение баланса недоступно')
        return redirect('accounts:profile')
    if request.method == 'POST':
        form = TopUpForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['final_amount']
            if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
                try:
                    from yookassa import Configuration, Payment as YKPayment
                    Configuration.account_id = settings.YOOKASSA_SHOP_ID
                    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
                    return_url = request.build_absolute_uri(reverse('accounts:payment_return'))
                    payment = YKPayment.create({
                        'amount': {'value': str(amount), 'currency': 'RUB'},
                        'confirmation': {'type': 'redirect', 'return_url': return_url},
                        'capture': True,
                        'description': f'Пополнение баланса — {request.user.phone_number}',
                        'metadata': {'user_id': request.user.id, 'amount': str(amount)},
                    })
                    request.session['yk_payment_id'] = payment.id
                    request.session['yk_amount'] = str(amount)
                    return redirect(payment.confirmation.confirmation_url)
                except Exception as e:
                    messages.error(request, f'Ошибка ЮКассы: {e}')
                    return render(request, 'accounts/topup.html', {'form': form})
            else:
                with transaction.atomic():
                    request.user.balance += amount
                    request.user.save(update_fields=['balance'])
                    BalanceTransaction.objects.create(
                        user=request.user,
                        amount=amount,
                        transaction_type=BalanceTransaction.TransactionType.TOPUP,
                        description=f'Пополнение баланса на {amount} ₽ (тестовый режим)'
                    )
                messages.success(request, f'Баланс пополнен на {amount} ₽ (ЮКасса не настроена — тест)')
                return redirect('accounts:profile')
    else:
        form = TopUpForm()
    yookassa_enabled = bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)
    return render(request, 'accounts/topup.html', {'form': form, 'yookassa_enabled': yookassa_enabled})


@login_required
def payment_return(request):
    payment_id = request.session.pop('yk_payment_id', None)
    amount_str = request.session.pop('yk_amount', None)
    if not payment_id:
        messages.error(request, 'Платёж не найден')
        return redirect('accounts:topup')
    try:
        from yookassa import Configuration, Payment as YKPayment
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
        payment = YKPayment.find_one(payment_id)
        if payment.status == 'succeeded':
            amount = Decimal(amount_str)
            with transaction.atomic():
                request.user.balance += amount
                request.user.save(update_fields=['balance'])
                BalanceTransaction.objects.create(
                    user=request.user,
                    amount=amount,
                    transaction_type=BalanceTransaction.TransactionType.TOPUP,
                    description=f'Пополнение через ЮКассу (ID: {payment_id[:12]})'
                )
            messages.success(request, f'Баланс успешно пополнен на {amount} ₽')
        elif payment.status in ('pending', 'waiting_for_capture'):
            messages.warning(request, 'Платёж обрабатывается. Баланс будет пополнен после подтверждения.')
        else:
            messages.error(request, 'Платёж не прошёл. Попробуйте ещё раз.')
    except Exception as e:
        messages.error(request, f'Ошибка проверки платежа: {e}')
    return redirect('accounts:profile')
