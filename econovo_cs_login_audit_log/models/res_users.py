from odoo import api, models
from odoo.http import request
from user_agents import parse


def _is_unbound_cs_audit_error(error):
    if str(error) not in ('object unbound', 'object is not bound'):
        return False

    audit_hook_completed = False
    local_proxy_failed = False
    traceback = error.__traceback__
    while traceback:
        frame = traceback.tb_frame
        module_name = frame.f_globals.get('__name__')
        method_name = frame.f_code.co_name
        if (
            module_name == 'odoo.addons.cs_login_audit_log.models.res_users'
            and method_name == '_check_credentials'
        ):
            audit_hook_completed = 'result' in frame.f_locals
        if (
            module_name == 'werkzeug.local'
            and method_name == '_get_current_object'
        ):
            local_proxy_failed = True
        traceback = traceback.tb_next

    return audit_hook_completed and local_proxy_failed


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _check_credentials(self, password, user_agent_env):
        """Preserve credential checks and tolerate the requestless audit hook."""
        try:
            return super()._check_credentials(password, user_agent_env)
        except RuntimeError as error:
            if (
                (user_agent_env or {}).get('interactive') is not False
                or not _is_unbound_cs_audit_error(error)
            ):
                raise
            return None

    @api.model
    def _log_successful_http_login(self, user_id):
        """Create an audit row from metadata available in the HTTP request."""
        user = self.sudo().browse(user_id).exists()
        if not user:
            return

        http_request = request.httprequest
        user_agent_string = http_request.headers.get('User-Agent')
        user_agent = parse(user_agent_string or '')
        session_id = getattr(request.session, 'sid', None)
        audit_model = self.env['cs.login.audit'].sudo()
        device_type = (
            'Mobile' if user_agent.is_mobile else
            'Tablet' if user_agent.is_tablet else
            'PC' if user_agent.is_pc else
            'Bot' if user_agent.is_bot else
            'Unknown'
        )

        values = {
            'user_id': user.id,
            'login_email': user.login,
            'ip_address': http_request.remote_addr,
            'user_agent': user_agent_string,
            'session_id': session_id,
            'company_id': user.company_id.id or False,
            'company_name': user.company_id.name or False,
            'db_name': request.db or request.session.db,
            'lang': user.lang,
            'tz': user.tz,
            'is_admin': user.has_group('base.group_system'),
            'device_type': device_type,
            'browser': user_agent.browser.family,
            'os': user_agent.os.family,
        }
        existing_audit = audit_model.search([
            ('user_id', '=', user.id),
            ('session_id', '=', session_id),
        ], limit=1) if session_id else audit_model
        if existing_audit:
            existing_audit.write(values)
        else:
            audit_model.create(values)