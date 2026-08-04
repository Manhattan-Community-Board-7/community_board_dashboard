from apig_wsgi import make_lambda_handler

from flask_app import app

# flask_app.py is the single source of truth for every route, auth check,
# and validation - this just adapts API Gateway's Lambda proxy events to
# WSGI calls against that same Flask app. For HTTP API v2 events (what this
# app receives - see README), apig-wsgi always enables binary support, and
# its default non-binary content-type list already treats text/*  and
# application/json as text while base64-encoding everything else (e.g.
# image/webp for favicon.webp) - no extra config needed here.
lambda_handler = make_lambda_handler(app)
