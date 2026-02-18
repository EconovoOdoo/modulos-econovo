# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from . import models


def _create_comex_sequences(env):
    """Post-init hook: create COMEX sequences and stock infrastructure."""
    env['res.company'].create_missing_comex_sequences()
    env['res.company'].create_missing_comex_stock_infrastructure()
