"""Single source of truth for DJANGO_SETTINGS_MODULE"""

from os import environ

environ.setdefault('DJANGO_SETTINGS_MODULE', 'demodj.settings')
