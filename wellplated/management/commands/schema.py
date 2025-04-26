from pathlib import Path
from subprocess import check_output

from django.conf import settings
from django.core.management.base import BaseCommand
from sqlfluff import fix


class Command(BaseCommand):
    """Export SQLite schema"""

    def handle(self, *args, **options):
        output = Path(__file__).parent.parent.parent / 'models.sql'
        print(f'Generating {output}')
        raw = check_output(
            ('sqlite3', settings.DATABASES['default']['NAME'], '.schema wellplated_*')
        ).decode()
        # sqlparse.format doesn't do a good enough job
        formatted = fix(raw, 'sqlite')
        output.write_text(formatted)
