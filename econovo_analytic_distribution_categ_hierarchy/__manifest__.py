{
    'name': 'Analytic Distribution - Category Hierarchy',
    'version': '17.0.1.0.0',
    'summary': 'Allows analytic distribution models to apply to subcategories of the configured product category.',
    'description': """
Analytic Distribution - Category Hierarchy
===========================================
Extends ``account.analytic.distribution.model`` with a per-rule opt-in flag
**Include Product Subcategories?**.

When enabled on a rule:

- The rule matches products whose category is the configured category
  **or any of its descendant categories**.
- Scoring is depth-aware: a rule on a more specific (deeper) ancestor
  always wins over a rule on a broader (shallower) ancestor.
  Exact category matches still score highest (1.0).

Example
-------
Rule: ``Product Category = Materials``, ``Include Product Subcategories? = True``

Applies to products in: *Materials*, *Materials / Metals*,
*Materials / Metals / Steel*, etc.

Rules without the flag enabled behave exactly as in standard Odoo
(exact category match only). Fully backward-compatible.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_analytic_distribution_model_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
