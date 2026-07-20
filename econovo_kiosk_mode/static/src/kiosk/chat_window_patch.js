/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ThreadService } from "@mail/core/common/thread_service";
import { kioskState } from "./kiosk_state";

/**
 * Kiosk mode: a kiosk screen has no menu/systray/Discuss sidebar to act
 * on a chat window anyway, so the only real trigger left is an incoming
 * message auto-opening a popup for the logged-in kiosk user - which is
 * exactly what `notifyMessageToUser` decides. Suppressing it here (and
 * only here) is enough: every other place that opens a chat window
 * requires a UI affordance (messaging menu, Discuss sidebar, ...) that
 * doesn't exist in the kiosk's chromeless full-screen shell.
 *
 * The underlying message is still received and stored as usual; only
 * the disruptive/potentially private floating popup is skipped.
 *
 * Reads `kioskState` (kept fresh by kiosk_chrome_service.js) rather than
 * `currentController.action.kiosk_hide_chat_window` directly, since the
 * latter is cached by the web client and can go stale - see
 * kiosk_state.js for the full explanation.
 */
patch(ThreadService.prototype, {
    notifyMessageToUser(thread, message) {
        const controller = this.env.services.action.currentController;
        // TEMPORARY diagnostic (2026-07): remove once the "chat still
        // shows in kiosk mode" report is confirmed fixed. Check via the
        // browser console when reproducing.
        console.debug("[econovo_kiosk_mode] notifyMessageToUser check", {
            currentActionId: controller?.action?.id,
            currentActionType: controller?.action?.type,
            kioskStateActionId: kioskState.actionId,
            kioskStateHideChat: kioskState.hideChat,
        });
        if (controller?.action?.id === kioskState.actionId && kioskState.hideChat) {
            return;
        }
        super.notifyMessageToUser(...arguments);
    },
});
