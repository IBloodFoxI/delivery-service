from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_balancetransaction_new_types_withdrawalrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='courier_location_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время последней геопозиции'),
        ),
    ]
