/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ThreadService } from "@mail/core/common/thread_service";
import { kioskState } from "./kiosk_state";

/**
 * Kiosk mode: suppresses the chat window popup AND the native OS-level
 * desktop notification (see `outOfFocusService.notify()` inside the
 * original `notifyMessageToUser`) that would otherwise fire when a new
 * message arrives for the logged-in kiosk user.
 *
 * This only covers messages genuinely addressed to the user - it does
 * NOT stop mail's own cross-tab chat window sync (the
 * `discuss.Thread/fold_state` bus channel mirrors chat windows opened
 * in any of the user's OTHER tabs/windows into this one too, by
 * design). That second path is instead handled purely with CSS
 * (`.o-mail-ChatWindowContainer` hidden in kiosk_mode.scss), since it's
 * simpler and more robust to hide the container outright than to chase
 * every internal mechanism that can insert a chat window.
 *
 * The underlying message is still received and stored as usual; only
 * the popup/notification is skipped.
 *
 * Reads `kioskState` (kept fresh by kiosk_chrome_service.js) rather than
 * `currentController.action.kiosk_hide_chat_window` directly, since the
 * latter is cached by the web client and can go stale - see
 * kiosk_state.js for the full explanation.
 */
patch(ThreadService.prototype, {
    notifyMessageToUser(thread, message) {
        const controller = this.env.services.action.currentController;
        if (controller?.action?.id === kioskState.actionId && kioskState.hideChat) {
            return;
        }
        super.notifyMessageToUser(...arguments);
    },
});
