import logging
import sys
import uuid

from flask import g, has_request_context, request


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


def init_app_logging(app):
    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(logging.INFO if not app.debug else logging.DEBUG)
    app.logger.handlers = []
    app.logger.propagate = True

    @app.before_request
    def _set_request_id():
        g.request_id = str(uuid.uuid4())[:8]

    @app.after_request
    def _add_request_id_header(response):
        if has_request_context() and getattr(g, "request_id", None):
            response.headers.setdefault("X-Request-ID", g.request_id)
        return response
