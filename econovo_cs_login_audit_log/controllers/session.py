from odoo import http
from odoo.addons.web.controllers.session import Session
from odoo.http import request


class LoginAuditSession(Session):

    @http.route()
    def authenticate(self, db, login, password, base_location=None):
        """Audit a successful JSON web-session authentication."""
        response = super().authenticate(
            db, login, password, base_location=base_location
        )
        if isinstance(response, dict) and response.get('uid'):
            request.env['res.users']._log_successful_http_login(
                response['uid']
            )
        return response