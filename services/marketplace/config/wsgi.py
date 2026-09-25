"""The WSGI entry point, and where this process starts tracing.

Tracing is started here rather than in settings because settings are imported
by everything — tests, management commands, the migration job — and none of
those should open an exporter they will never use. gunicorn imports this
module inside each worker, which is also the only place a span processor's
thread is any use.
"""

import os

from django.core.wsgi import get_wsgi_application

from config.telemetry import configure_tracing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Before the application is built: the Django instrumentor patches the request
# handler, and a handler already built is a handler already unpatched.
configure_tracing("marketplace", django=True)

application = get_wsgi_application()
