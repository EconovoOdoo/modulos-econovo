/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ThreadService } from "@mail/core/common/thread_service";

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
 */
patch(ThreadService.prototype, {
    notifyMessageToUser(thread, message) {
        const controller = this.env.services.action.currentController;
        if (controller?.action?.kiosk_hide_chat_window) {
            return;
        }
        super.notifyMessageToUser(...arguments);
    },
});
