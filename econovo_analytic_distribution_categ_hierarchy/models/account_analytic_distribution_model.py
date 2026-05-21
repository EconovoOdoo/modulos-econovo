from odoo import fields, models
from odoo.addons.analytic.models.analytic_distribution_model import NonMatchingDistribution


class AccountAnalyticDistributionModel(models.Model):
    _inherit = 'account.analytic.distribution.model'

    product_categ_hierarchy = fields.Boolean(
        string='Include Subcategories',
        default=False,
        help='When enabled, this distribution model also applies to products '
             'in subcategories of the configured Product Category.\n\n'
             'Scoring is depth-aware: a rule on a closer (deeper) ancestor '
             'always wins over a rule on a broader (shallower) ancestor. '
             'Exact category matches always score highest.',
    )

    def _get_fields_to_check(self):
        """Exclude product_categ_hierarchy from condition scoring.

        This field is a configuration flag, not a filter condition like
        partner_id or product_id. Including it in the scoring loop would
        cause NonMatchingDistribution for all hierarchy-enabled rules,
        since 'product_categ_hierarchy' is never present in the vals dict
        passed to _get_distribution().
        """
        return super()._get_fields_to_check() - {'product_categ_hierarchy'}

    def _create_domain(self, fname, value):
        """Build search domain for product_categ_id respecting the hierarchy flag.

        For non-hierarchy rules (flag=False): exact match only, same as native Odoo.
        For hierarchy rules (flag=True): also include ancestor categories using
        the parent_of domain operator, which leverages the indexed parent_path field.

        Domain structure (Odoo prefix notation):
          (categ_id = False)                          -- rules with no category (always)
          OR (categ_id = value)                       -- exact match (always)
          OR (hierarchy=True AND categ_id parent_of value)  -- ancestor match opt-in
        """
        if fname != 'product_categ_id':
            return super()._create_domain(fname, value)

        if not value:
            return False

        return [
            '|', ('product_categ_id', '=', False),
            '|', ('product_categ_id', '=', value),
                 '&', ('product_categ_hierarchy', '=', True),
                      ('product_categ_id', 'parent_of', value),
        ]

    def _check_score(self, key, value):
        """Score category matches with hierarchy-aware fractional scoring.

        Comparison with native Odoo behavior
        -------------------------------------
        Native Odoo (_check_score base):
          - field not set → 0 (matches anything, lowest priority)
          - value == self[key].id → 1
          - otherwise → NonMatchingDistribution (rule excluded)

        This module (product_categ_id only):
          - field not set → 0  (unchanged)
          - exact match → 1  (unchanged)
          - product is in a subcategory of rule's category AND flag=True
            → depth_rule / depth_product  (float in (0, 1))
            Deeper ancestor = closer match = higher score.
            E.g. for Steel product (depth=4):
              rule Metals (depth=3) → 3/4 = 0.75
              rule Materials (depth=2) → 2/4 = 0.50
              rule All (depth=1) → 1/4 = 0.25
          - no match → NonMatchingDistribution  (unchanged)

        Edge cases handled
        ------------------
        - value is list/tuple: iterate and return score for first valid match.
        - value is falsy (product has no category): NonMatchingDistribution if
          the rule has a category set (can't match no-category product).
        - parent_path is None/empty (unpopulated tree): falls back to exact
          match only to avoid AttributeError.
        - depth_prod is 0: returns 1 to avoid ZeroDivisionError (shouldn't
          happen in practice since all categories have at least root path).
        """
        if key != 'product_categ_id':
            return super()._check_score(key, value)

        if not self.product_categ_id:
            # No category restriction on this rule: matches anything (generic).
            return 0

        categ_ids = value if isinstance(value, (list, tuple)) else ([value] if value else [])
        if not categ_ids:
            # Product has no category but rule requires one: exclude this rule.
            raise NonMatchingDistribution

        rule_path = self.product_categ_id.parent_path

        if not rule_path:
            # parent_path not populated (e.g. post-migration data): fall back
            # to exact match only to avoid incorrect hierarchy matching.
            if any(cid == self.product_categ_id.id for cid in categ_ids):
                return 1
            raise NonMatchingDistribution

        for categ_id in categ_ids:
            if not categ_id:
                continue

            if categ_id == self.product_categ_id.id:
                # Exact match: always valid, regardless of hierarchy flag.
                return 1

            if not self.product_categ_hierarchy:
                # Hierarchy disabled: only exact match is valid (native behavior).
                continue

            product_categ = self.env['product.category'].browse(categ_id)
            categ_path = product_categ.parent_path

            if not categ_path:
                # parent_path not populated for this category: skip.
                continue

            if categ_path.startswith(rule_path):
                # Product's category is a descendant of the rule's category.
                # Fractional score: deeper rule = closer match = higher score.
                # parent_path format "1/2/3/" → count('/') = depth level.
                depth_rule = rule_path.count('/')
                depth_prod = categ_path.count('/')
                return depth_rule / depth_prod if depth_prod else 1

        raise NonMatchingDistribution
