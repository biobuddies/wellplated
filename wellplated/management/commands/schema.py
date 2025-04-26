from pathlib import Path
from subprocess import check_output
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from sqlfluff import fix
from sqlfluff.core.config import FluffConfig


class Command(BaseCommand):
    help = """Export SQLite schema"""

    def handle(self, *_args: Any, **_kwargs: Any) -> None:
        output = Path(__file__).parent.parent.parent / 'models.sql'
        print(f'Generating {output}')
        # sqlparse.format doesn't do a good enough job
        # Temporarily commenting out unsigned works around https://github.com/sqlfluff/sqlfluff/issues/6844
        raw = (
            check_output(  # noqa: S603
                ('sqlite3', 'db.sqlite3', '.schema wellplated_*')
            )
            .decode()
            .replace('unsigned', '/*unsigned*/')
        )
        formatted = fix(
            raw,
            'sqlite',
            config=FluffConfig({'core': {'dialect': 'sqlite', 'max_line_length': 100}}),
        ).replace('/*unsigned*/', 'unsigned')
        output.write_text(formatted)
