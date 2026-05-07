from django.db import models
from django.utils import timezone
from datetime import timedelta


class BackupSettings(models.Model):
    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Ежедневно'
        WEEKLY = 'weekly', 'Еженедельно'
        MONTHLY = 'monthly', 'Ежемесячно'

    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.WEEKLY)
    is_enabled = models.BooleanField(default=True)
    max_backups = models.PositiveIntegerField(default=10)
    last_backup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Настройки резервного копирования'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def should_run_now(self):
        if not self.is_enabled:
            return False
        if self.last_backup_at is None:
            return True
        delta = {
            self.Frequency.DAILY: timedelta(days=1),
            self.Frequency.WEEKLY: timedelta(weeks=1),
            self.Frequency.MONTHLY: timedelta(days=30),
        }[self.frequency]
        return timezone.now() >= self.last_backup_at + delta


class BackupRecord(models.Model):
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Резервная копия'
        verbose_name_plural = 'Резервные копии'

    def __str__(self):
        return self.filename

    @property
    def size_display(self):
        size = self.file_size
        for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} ГБ'
