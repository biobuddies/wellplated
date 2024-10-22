"""
ASGI config for demodj project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

from django.core.asgi import get_asgi_application

from default import settings_module  # noqa: F401

application = get_asgi_application()
