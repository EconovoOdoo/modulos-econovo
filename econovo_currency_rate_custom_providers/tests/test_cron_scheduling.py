# -*- coding: utf-8 -*-
"""Minimal tests for cron scheduling functionality.

These tests verify that cron is created correctly when auto_update is enabled.
"""

import uuid
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCronCreation(TransactionCase):
    """Test automatic cron creation."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        super().setUpClass()
        
        # Enable the module functionality (required for cron creation)
        cls.env['ir.config_parameter'].sudo().set_param(
            'econovo_currency_rate_custom_providers.enabled', 'True'
        )
        
        # Unique suffix for test data
        cls._test_uid = str(uuid.uuid4())[:8]
        
        # Get currencies
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_ars = cls.env['res.currency'].search(
            [('name', '=', 'ARS')], limit=1
        ) or cls.env.ref('base.EUR')

    def test_01_cron_created_when_auto_update_enabled(self):
        """Verify ir.cron is created when auto_update=True."""
        unique_name = f'Test Cron Source {uuid.uuid4().hex[:8]}'
        
        source = self.env['currency.rate.source'].create({
            'name': unique_name,
            'source_currency_id': self.currency_usd.id,
            'target_currency_id': self.currency_ars.id,
            'url': 'https://api.example.com/rate',
            'response_type': 'json',
            'extraction_method': 'jsonpath',
            'jsonpath_expression': '$.rate',
            'auto_update': True,
            'active': True,
            'update_frequency': 'daily',
        })
        
        self.assertTrue(
            source.cron_id,
            "Cron should be created when auto_update=True"
        )
        self.assertTrue(
            source.cron_id.active,
            "Cron should be active"
        )

    def test_02_no_cron_when_auto_update_disabled(self):
        """Verify no cron is created when auto_update=False."""
        unique_name = f'Test No Cron Source {uuid.uuid4().hex[:8]}'
        
        source = self.env['currency.rate.source'].create({
            'name': unique_name,
            'source_currency_id': self.currency_usd.id,
            'target_currency_id': self.currency_ars.id,
            'url': 'https://api.example.com/rate',
            'response_type': 'json',
            'extraction_method': 'jsonpath',
            'jsonpath_expression': '$.rate',
            'auto_update': False,
        })
        
        self.assertFalse(
            source.cron_id,
            "No cron should be created when auto_update=False"
        )
