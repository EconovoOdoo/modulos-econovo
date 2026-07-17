# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Earlier versions of this module forced `target='fullscreen'` on the
    action record itself (via an onchange) when Kiosk Mode was enabled,
    and never reverted it back on toggle-off - a permanent side effect
    on a core, shared field (`ir.actions.act_window.target`) that
    survives even this module's own uninstall, since uninstalling only
    removes the fields this module defines, not values it previously
    wrote into core ones.

    From this version on, the full-screen look is achieved purely
    through CSS (see static/src/kiosk/kiosk_mode.scss, `.o_navbar`),
    without touching `target` at all. Clean up any action still stuck
    in the old state.
    """
    cr.execute("""
        UPDATE ir_actions_act_window
           SET target = NULL
         WHERE target = 'fullscreen'
           AND kiosk_enabled IS TRUE
    """)
