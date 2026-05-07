from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_addr_lat_order_addr_lon'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_fee',
            field=models.DecimalField(decimal_places=2, default=100, max_digits=8, verbose_name='Стоимость доставки'),
        ),
        migrations.AddField(
            model_name='order',
            name='yookassa_payment_id',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='ID платежа ЮКасса'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('payment_pending', 'Ожидает оплаты'),
                    ('pending', 'Ожидает курьера'),
                    ('assigned', 'Курьер назначен'),
                    ('in_progress', 'В пути'),
                    ('delivered', 'Доставлен'),
                    ('cancelled', 'Отменён'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
    ]
