# -*- coding: utf-8 -*-
"""HTTP controller override: accept classic form-encoded webhook bodies.

base_automation's own /web/hook/<uuid> endpoint only parses the request body
as JSON, falling back to the URL query string only. Some external no-code
tools (Elementor Pro's native "Webhook" form action, for example) POST a
classic application/x-www-form-urlencoded body instead, so that endpoint
always saw an empty payload. This override adds one extra fallback, the
parsed form body, used only when neither JSON nor the query string produced
anything.
"""

from odoo.http import request, route
from odoo.addons.base_automation.controllers.main import BaseAutomationController as BaseAutomationControllerOrigin
from odoo.addons.base_automation.models.base_automation import get_webhook_request_payload


class BaseAutomationController(BaseAutomationControllerOrigin):

    @route(['/web/hook/<string:rule_uuid>'], type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def call_webhook_http(self, rule_uuid, **kwargs):
        """ Execute an automation webhook """
        rule = request.env['base.automation'].sudo().search([('webhook_uuid', '=', rule_uuid)])
        if not rule:
            return request.make_json_response({'status': 'error'}, status=404)

        data = get_webhook_request_payload()
        if not data and request.httprequest.form:
            # Elementor Pro (and other no-code form builders) POST a classic
            # form body instead of JSON, which get_webhook_request_payload()
            # cannot parse - fall back to the form data Werkzeug already parsed.
            data = request.httprequest.form.to_dict()
        try:
            rule._execute_webhook(data)
        except Exception:  # noqa: BLE001
            return request.make_json_response({'status': 'error'}, status=500)
        return request.make_json_response({'status': 'ok'}, status=200)
