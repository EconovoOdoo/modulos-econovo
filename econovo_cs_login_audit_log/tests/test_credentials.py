from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command
from odoo.addons.cs_login_audit_log.models.res_users import (
    ResUsers as CsLoginAuditResUsers,
)
from odoo.exceptions import AccessDenied
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLoginAuditCredentials(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Login Audit Test User',
            'login': 'login-audit-test-user',
            'password': 'valid-test-password',
            'groups_id': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def test_non_interactive_check_without_http_context(self):
        self.user.with_user(self.user)._check_credentials(
            'valid-test-password',
            {'interactive': False},
        )
        audit_count = self.env['cs.login.audit'].sudo().search_count([
            ('user_id', '=', self.user.id),
        ])
        self.assertEqual(audit_count, 0)

    def test_non_interactive_check_still_rejects_invalid_password(self):
        with self.assertRaises(AccessDenied):
            self.user.with_user(self.user)._check_credentials(
                'invalid-test-password',
                {'interactive': False},
            )

    def test_same_runtime_error_from_other_hook_is_not_suppressed(self):
        def raise_before_super(user, password, user_agent_env):
            raise RuntimeError('object is not bound')

        with patch.object(
            CsLoginAuditResUsers,
            '_check_credentials',
            raise_before_super,
        ):
            with self.assertRaisesRegex(RuntimeError, 'object is not bound'):
                self.user.with_user(self.user)._check_credentials(
                    'valid-test-password',
                    {'interactive': False},
                )

    def test_unbound_request_error_is_not_suppressed_for_interactive_check(self):
        with self.assertRaisesRegex(RuntimeError, 'object .*not bound|object unbound'):
            self.user.with_user(self.user)._check_credentials(
                'valid-test-password',
                {'interactive': True},
            )

    def test_http_login_audit_records_request_metadata(self):
        request_context = SimpleNamespace(
            httprequest=SimpleNamespace(
                headers={'User-Agent': 'Mozilla/5.0'},
                remote_addr='192.0.2.15',
            ),
            session=SimpleNamespace(sid='login-audit-test-session'),
            db=self.env.cr.dbname,
        )
        self.env['cs.login.audit'].sudo().create({
            'user_id': self.user.id,
            'login_email': self.user.login,
            'ip_address': '198.51.100.20',
            'session_id': 'login-audit-test-session',
        })

        with patch(
            'odoo.addons.econovo_cs_login_audit_log.models.res_users.request',
            request_context,
        ):
            self.env['res.users']._log_successful_http_login(self.user.id)

        audit = self.env['cs.login.audit'].sudo().search([
            ('user_id', '=', self.user.id),
            ('session_id', '=', 'login-audit-test-session'),
        ], limit=1)
        self.assertTrue(audit)
        self.assertEqual(
            self.env['cs.login.audit'].sudo().search_count([
                ('user_id', '=', self.user.id),
                ('session_id', '=', 'login-audit-test-session'),
            ]),
            1,
        )
        self.assertEqual(audit.ip_address, '192.0.2.15')
        self.assertEqual(audit.user_agent, 'Mozilla/5.0')
        self.assertEqual(audit.db_name, self.env.cr.dbname)