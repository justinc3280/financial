from flask import render_template, request

from app.errors import errors
from app.api.routes import error_response


@errors.app_errorhandler(404)
def not_found_error(code):
    if (
        request.accept_mimetypes['application/json']
        >= request.accept_mimetypes['text/html']
    ):
        return error_response(404, message='URL not found')
    else:
        return render_template('errors/error_404.html'), 404
