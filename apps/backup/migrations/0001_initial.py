from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BackupSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.CharField(
                    choices=[('daily', 'Ежедневно'), ('weekly', 'Еженедельно'), ('monthly', 'Ежемесячно')],
                    default='weekly', max_length=10)),
                ('is_enabled', models.BooleanField(default=True)),
                ('max_backups', models.PositiveIntegerField(default=10)),
                ('last_backup_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Настройки резервного копирования',
            },
        ),
        migrations.CreateModel(
            name='BackupRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('file_size', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.CharField(blank=True, max_length=500)),
            ],
            options={
                'verbose_name': 'Резервная копия',
                'verbose_name_plural': 'Резервные копии',
                'ordering': ['-created_at'],
            },
        ),
    ]
