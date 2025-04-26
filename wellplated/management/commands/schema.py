from pathlib import Path
from subprocess import check_output

from django.conf import settings
from django.core.management.base import BaseCommand
from sqlfluff import fix
from sqlfluff.core.config import FluffConfig


class Command(BaseCommand):
    """Export SQLite schema"""

    def handle(self, *args, **options):
        output = Path(__file__).parent.parent.parent / 'models.sql'
        print(f'Generating {output}')
        raw = check_output(
            ('sqlite3', settings.DATABASES['default']['NAME'], '.schema wellplated_*')
        ).decode().replace('unsigned', '/*unsigned*/')
        # sqlparse.format doesn't do a good enough job
        # Workaround https://github.com/sqlfluff/sqlfluff/issues/6844
        formatted = fix(raw, 'sqlite', config=FluffConfig({'core': {'dialect': 'sqlite', 'max_line_length': 100}})).replace('/*unsigned*/', 'unsigned')
        output.write_text(formatted)
