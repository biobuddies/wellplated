"""
WSGI config for demodj project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

from django.core.wsgi import get_wsgi_application

from default import settings_module  # noqa: F401

application = get_wsgi_application()
