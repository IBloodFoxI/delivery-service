from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 1 of 3: add hash fields WITHOUT unique constraint (hashes are still empty)."""

    dependencies = [
        ('accounts', '0004_user_courier_location_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64,
                                   verbose_name='Хэш телефона', default=''),
        ),
        migrations.AddField(
            model_name='user',
            name='email_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64,
                                   verbose_name='Хэш email', default=''),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.TextField(verbose_name='Номер телефона (зашифрован)', default=''),
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.TextField(blank=True, default='', verbose_name='Email (зашифрован)'),
        ),
    ]
