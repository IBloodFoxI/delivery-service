import time
import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the backup scheduler (infinite loop, checks every 60 seconds)'

    def handle(self, *args, **options):
        self.stdout.write('Backup scheduler started.')
        while True:
            try:
                from apps.backup.models import BackupSettings
                cfg = BackupSettings.get()
                if cfg.should_run_now():
                    self.stdout.write('Scheduled backup triggered.')
                    call_command('backup_db', notes='Auto backup')
            except Exception as e:
                logger.error(f'Scheduler error: {e}')
                self.stderr.write(f'Error: {e}')
            time.sleep(60)
