from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import request


class LoginAuditHome(Home):

    @http.route()
    def web_login(self, redirect=None, **kw):
        """Audit a successful browser form login after the core flow returns."""
        response = super().web_login(redirect=redirect, **kw)
        if request.params.get('login_success') and request.session.uid:
            request.env['res.users']._log_successful_http_login(
                request.session.uid
            )
        return response