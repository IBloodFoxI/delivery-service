from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone_number, full_name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Номер телефона обязателен')
        user = self.model(full_name=full_name, **extra_fields)
        user.phone_number = phone_number          # triggers encryption via setter
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self.create_user(phone_number, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Покупатель'
        COURIER = 'courier', 'Курьер'
        SUPPORT = 'support', 'Тех. поддержка'
        ADMIN = 'admin', 'Администратор'

    # ── Зашифрованные поля (хранятся в БД в виде ciphertext) ──────────────
    # phone_number хранит зашифрованный номер; phone_hash — HMAC для поиска/уникальности
    phone_number = models.TextField(verbose_name='Номер телефона (зашифрован)')
    phone_hash   = models.CharField(max_length=64, unique=True, db_index=True, blank=True,
                                    verbose_name='Хэш телефона')
    # email хранит зашифрованный адрес; email_hash — HMAC для проверки уникальности
    email        = models.TextField(blank=True, default='', verbose_name='Email (зашифрован)')
    email_hash   = models.CharField(max_length=64, db_index=True, blank=True,
                                    verbose_name='Хэш email')
    full_name = models.CharField(max_length=255, verbose_name='ФИО')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER, verbose_name='Роль')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Баланс')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    courier_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Широта курьера')
    courier_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Долгота курьера')
    courier_location_at = models.DateTimeField(null=True, blank=True, verbose_name='Время последней геопозиции')

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    # ── Прозрачное шифрование при чтении/записи ───────────────────────────

    def get_phone(self) -> str:
        from .crypto import decrypt
        return decrypt(self.phone_number)

    def set_phone(self, value: str):
        from .crypto import encrypt, make_hash
        self.phone_number = encrypt(value)
        self.phone_hash = make_hash(value)

    def get_email_plain(self) -> str:
        from .crypto import decrypt
        return decrypt(self.email)

    def set_email_encrypted(self, value: str):
        from .crypto import encrypt, make_hash
        self.email = encrypt(value) if value else ''
        self.email_hash = make_hash(value) if value else ''

    def save(self, *args, **kwargs):
        from .crypto import encrypt, make_hash
        # Автошифрование: если значение выглядит как открытый текст — шифруем
        if self.phone_number and not self.phone_number.startswith('gAAA'):
            raw = self.phone_number
            self.phone_number = encrypt(raw)
            self.phone_hash = make_hash(raw)
        if self.email and not self.email.startswith('gAAA'):
            raw = self.email
            self.email = encrypt(raw)
            self.email_hash = make_hash(raw)
        super().save(*args, **kwargs)

    @property
    def phone_display(self) -> str:
        """Расшифрованный номер телефона для отображения в UI."""
        return self.get_phone()

    @property
    def email_display(self) -> str:
        """Расшифрованный email для отображения в UI."""
        return self.get_email_plain()

    def __str__(self):
        return f'{self.full_name} ({self.phone_display})'

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_courier(self):
        return self.role == self.Role.COURIER

    @property
    def is_support(self):
        return self.role == self.Role.SUPPORT

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN


class BalanceTransaction(models.Model):
    class TransactionType(models.TextChoices):
        TOPUP = 'topup', 'Пополнение'
        PAYMENT = 'payment', 'Оплата заказа'
        REFUND = 'refund', 'Возврат'
        EARNING = 'earning', 'Заработок'
        WITHDRAWAL = 'withdrawal', 'Вывод средств'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', verbose_name='Пользователь')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name='Тип')
    description = models.CharField(max_length=255, blank=True, verbose_name='Описание')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.amount} ({self.get_transaction_type_display()})'


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        PROCESSING = 'processing', 'В обработке'
        DONE = 'done', 'Выполнен'
        REJECTED = 'rejected', 'Отклонён'

    courier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals', verbose_name='Курьер')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    phone = models.CharField(max_length=20, verbose_name='Телефон для СБП')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    yookassa_payout_id = models.CharField(max_length=100, blank=True, default='', verbose_name='ID выплаты ЮКасса')
    admin_note = models.CharField(max_length=500, blank=True, verbose_name='Примечание администратора')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Обработан')

    class Meta:
        verbose_name = 'Запрос на вывод'
        verbose_name_plural = 'Запросы на вывод'
        ordering = ['-created_at']

    def __str__(self):
        return f'Вывод {self.amount} ₽ — {self.courier.full_name}'
