import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_courier_lat_user_courier_lon_user_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='balancetransaction',
            name='transaction_type',
            field=models.CharField(
                choices=[
                    ('topup', 'Пополнение'),
                    ('payment', 'Оплата заказа'),
                    ('refund', 'Возврат'),
                    ('earning', 'Заработок'),
                    ('withdrawal', 'Вывод средств'),
                ],
                max_length=20,
                verbose_name='Тип',
            ),
        ),
        migrations.CreateModel(
            name='WithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма')),
                ('phone', models.CharField(max_length=20, verbose_name='Телефон для СБП')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Ожидает'),
                        ('processing', 'В обработке'),
                        ('done', 'Выполнен'),
                        ('rejected', 'Отклонён'),
                    ],
                    default='pending',
                    max_length=15,
                    verbose_name='Статус',
                )),
                ('yookassa_payout_id', models.CharField(blank=True, default='', max_length=100, verbose_name='ID выплаты ЮКасса')),
                ('admin_note', models.CharField(blank=True, max_length=500, verbose_name='Примечание администратора')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Обработан')),
                ('courier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='withdrawals',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Курьер',
                )),
            ],
            options={
                'verbose_name': 'Запрос на вывод',
                'verbose_name_plural': 'Запросы на вывод',
                'ordering': ['-created_at'],
            },
        ),
    ]
