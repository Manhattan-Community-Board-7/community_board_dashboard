from apig_wsgi import make_lambda_handler

from flask_app import app

# flask_app.py is the single source of truth for every route, auth check,
# and validation - this just adapts API Gateway's Lambda proxy events to
# WSGI calls against that same Flask app. For HTTP API v2 events (what this
# app receives - see README), apig-wsgi always enables binary support, and
# its default non-binary content-type list already treats text/* and
# application/json as text while base64-encoding everything else (e.g.
# image/webp for favicon.webp) - no extra config needed here.
_wsgi_handler = make_lambda_handler(app)


def lambda_handler(event, context):
    # This API Gateway stage is named "default" (not the special reserved
    # $default stage AWS treats as path-prefix-free), so despite the custom
    # domain's empty base-path mapping, every real event's rawPath still
    # arrives with a literal "/default" prefix (e.g. "/default/results").
    # Strip it before Flask ever sees the path, or nothing routes.
    path = event.get('rawPath', '')
    if path == '/default' or path.startswith('/default/'):
        event['rawPath'] = path[len('/default'):] or '/'
    return _wsgi_handler(event, context)
