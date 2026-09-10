# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWebhookFormData(HttpCase):

    def test_webhook_accepts_form_urlencoded_body(self):
        """ A rule's record_getter must see the fields of a classic
        application/x-www-form-urlencoded body, mirroring the real payload
        shape sent by Elementor Pro's native Webhook form action. """
        automation = self.env['base.automation'].create({
            'name': 'Test form-encoded webhook',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'trigger': 'on_webhook',
            'record_getter': "model.create({'name': payload.get('fields[name][value]') or 'no-name'})",
        })
        body = 'fields%5Bname%5D%5Bvalue%5D=Juan+Perez+Test'
        response = self.url_open(
            '/web/hook/%s' % automation.webhook_uuid,
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        self.assertEqual(response.status_code, 200)
        partner = self.env['res.partner'].search([('name', '=', 'Juan Perez Test')])
        self.assertTrue(partner, "Expected a res.partner created from the form-encoded webhook payload")

    def test_webhook_still_accepts_json_body(self):
        """ The pre-existing JSON path must keep working (no regression). """
        automation = self.env['base.automation'].create({
            'name': 'Test JSON webhook',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'trigger': 'on_webhook',
            'record_getter': "model.create({'name': payload.get('name') or 'no-name'})",
        })
        response = self.url_open(
            '/web/hook/%s' % automation.webhook_uuid,
            data='{"name": "Json Test Partner"}',
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200)
        partner = self.env['res.partner'].search([('name', '=', 'Json Test Partner')])
        self.assertTrue(partner, "Expected a res.partner created from the JSON webhook payload")
