# -*- coding: utf-8 -*-
"""Minimal tests for notifications functionality.

These tests verify that the notification configuration fields work correctly.
"""

import uuid
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNotificationConfig(TransactionCase):
    """Test notification configuration."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        super().setUpClass()
        
        # Enable the module functionality by assigning the group to admin user
        group = cls.env.ref(
            'econovo_currency_rate_custom_providers.group_custom_rate_sources'
        )
        group.sudo().write({'users': [(4, cls.env.ref('base.user_admin').id)]})
        
        # Unique suffix for test data
        cls._test_uid = str(uuid.uuid4())[:8]
        
        # Get currencies
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_ars = cls.env['res.currency'].search(
            [('name', '=', 'ARS')], limit=1
        ) or cls.env.ref('base.EUR')
        
        # Create test partner
        cls.partner = cls.env['res.partner'].create({
            'name': f'Test Partner {cls._test_uid}',
            'email': f'test.{cls._test_uid}@example.com',
        })

    def test_01_notification_fields_exist(self):
        """Verify notification fields are present on the model."""
        model = self.env['currency.rate.source']
        
        # Check required fields exist
        self.assertIn('notify_on_error', model._fields)
        self.assertIn('notify_partner_ids', model._fields)
        self.assertIn('notify_user_ids', model._fields)
        self.assertIn('notify_channel_id', model._fields)

    def test_02_create_source_with_notifications(self):
        """Verify source can be created with notification settings."""
        unique_name = f'Test Notify Source {uuid.uuid4().hex[:8]}'
        
        source = self.env['currency.rate.source'].create({
            'name': unique_name,
            'source_currency_id': self.currency_usd.id,
            'target_currency_id': self.currency_ars.id,
            'url': 'https://api.example.com/rate',
            'response_type': 'json',
            'extraction_method': 'jsonpath',
            'jsonpath_expression': '$.rate',
            'auto_update': False,
            'notify_on_error': True,
            'notify_partner_ids': [(4, self.partner.id)],
        })
        
        self.assertTrue(source.notify_on_error)
        self.assertIn(self.partner, source.notify_partner_ids)
