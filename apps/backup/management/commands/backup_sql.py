import gzip
import os
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create a SQL database backup using pg_dump'

    def add_arguments(self, parser):
        parser.add_argument('--notes', type=str, default='', help='Optional notes for this backup')

    def handle(self, *args, **options):
        from apps.backup.models import BackupRecord, BackupSettings

        backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
        os.makedirs(backup_dir, exist_ok=True)

        db = settings.DATABASES['default']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_sql_{timestamp}.sql.gz'
        filepath = os.path.join(backup_dir, filename)

        self.stdout.write(f'Creating SQL backup: {filename}')

        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        cmd = [
            'pg_dump',
            '-h', db.get('HOST', 'db'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', 'postgres'),
            '-d', db.get('NAME', 'postgres'),
            '--no-owner',
            '--no-acl',
        ]

        result = subprocess.run(cmd, capture_output=True, env=env)
        if result.returncode != 0:
            self.stderr.write(f'pg_dump failed: {result.stderr.decode()}')
            raise Exception(f'pg_dump error: {result.stderr.decode()}')

        with gzip.open(filepath, 'wb') as f:
            f.write(result.stdout)

        file_size = os.path.getsize(filepath)

        record = BackupRecord.objects.create(
            filename=filename,
            file_size=file_size,
            notes=options.get('notes', ''),
        )

        cfg = BackupSettings.get()
        cfg.last_backup_at = timezone.now()
        cfg.save(update_fields=['last_backup_at'])

        # Prune old SQL backups
        sql_records = BackupRecord.objects.filter(filename__startswith='backup_sql_').order_by('-created_at')
        for old in sql_records[cfg.max_backups:]:
            old_path = os.path.join(backup_dir, old.filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            old.delete()

        self.stdout.write(self.style.SUCCESS(
            f'SQL backup created: {filename} ({file_size} bytes)'
        ))
