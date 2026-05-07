import gzip
import os
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create a database backup using dumpdata'

    def add_arguments(self, parser):
        parser.add_argument('--notes', type=str, default='', help='Optional notes for this backup')

    def handle(self, *args, **options):
        from apps.backup.models import BackupRecord, BackupSettings

        backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.json.gz'
        filepath = os.path.join(backup_dir, filename)

        self.stdout.write(f'Creating backup: {filename}')

        buf = StringIO()
        call_command(
            'dumpdata',
            '--natural-foreign',
            '--natural-primary',
            '--exclude=contenttypes',
            '--exclude=auth.permission',
            '--exclude=backup',
            '--indent=2',
            stdout=buf,
        )

        data = buf.getvalue().encode('utf-8')
        with gzip.open(filepath, 'wb') as f:
            f.write(data)

        file_size = os.path.getsize(filepath)

        record = BackupRecord.objects.create(
            filename=filename,
            file_size=file_size,
            notes=options.get('notes', ''),
        )

        cfg = BackupSettings.get()
        cfg.last_backup_at = timezone.now()
        cfg.save(update_fields=['last_backup_at'])

        # Prune old backups if over the limit
        max_backups = cfg.max_backups
        all_records = BackupRecord.objects.order_by('-created_at')
        to_delete = all_records[max_backups:]
        for old in to_delete:
            old_path = os.path.join(backup_dir, old.filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            old.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Backup created: {filename} ({file_size} bytes, record id={record.pk})'
        ))
