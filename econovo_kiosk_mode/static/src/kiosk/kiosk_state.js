/** @odoo-module **/

/**
 * Small shared, synchronous snapshot of the kiosk fields for whichever
 * action is currently displayed, kept fresh by `kiosk_chrome_service.js`
 * via a dedicated RPC (`ir.actions.act_window.get_kiosk_state`) on every
 * action update.
 *
 * Why this exists: the web client caches the loaded action dict per
 * browser tab (action_service.js `actionCache`), so
 * `currentController.action.kiosk_hide_chat_window` can go stale after
 * the action record is edited - see `ir_actions_act_window.py`
 * `_get_readable_fields` for the full explanation. `chat_window_patch.js`
 * reads this object instead of the (cacheable) action fields.
 */
export const kioskState = {
    actionId: null,
    hideChat: false,
};
