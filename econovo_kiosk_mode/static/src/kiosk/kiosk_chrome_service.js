/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

// Even in "realtime" mode, force a safety-net refresh periodically: a
// screen left open for many hours must not rely purely on push, in case
// a bus message is ever missed (worker restart, network blip) - see
// module README for the full rationale.
const KIOSK_SAFETY_INTERVAL_MS = 5 * 60 * 1000;
// Debounce refreshes so a burst of bus notifications (e.g. a bulk
// import on the watched model) triggers at most one reload.
const KIOSK_REFRESH_DEBOUNCE_MS = 2000;
const KIOSK_BODY_CLASS = "o_kiosk_mode";

/**
 * Generic kiosk "chrome + refresh" controller. Reacts to whichever
 * action is currently displayed: if it has `kiosk_enabled`, toggles the
 * full-screen kiosk styling and wires up the configured refresh
 * strategy (bus-based real time, or a plain interval). Works for any
 * action/model/view type since it never touches view-specific code -
 * it only calls back into the standard action service.
 */
export const kioskChromeService = {
    dependencies: ["action", "bus_service"],
    start(env, { action, bus_service }) {
        let refreshTimer = null;
        let safetyTimer = null;
        let debounceTimer = null;
        let subscribedModel = null;

        const clearTimers = () => {
            browser.clearInterval(refreshTimer);
            browser.clearInterval(safetyTimer);
            browser.clearTimeout(debounceTimer);
            refreshTimer = null;
            safetyTimer = null;
            debounceTimer = null;
        };

        const unsubscribeModel = () => {
            if (subscribedModel) {
                bus_service.deleteChannel(`kiosk_refresh-${subscribedModel}`);
                subscribedModel = null;
            }
        };

        const reload = (kioskAction) => {
            debounceTimer = null;
            // Only reload if that action is still the one on screen.
            if (action.currentController?.action?.id === kioskAction.id) {
                action.doAction(kioskAction.id, { clearBreadcrumbs: true });
            }
        };

        const scheduleReload = (kioskAction) => {
            if (!debounceTimer) {
                debounceTimer = browser.setTimeout(
                    () => reload(kioskAction),
                    KIOSK_REFRESH_DEBOUNCE_MS
                );
            }
        };

        // Custom notification type sent by `ir.actions.act_window._kiosk_notify`.
        bus_service.subscribe("kiosk_refresh", (payload) => {
            const currentAction = action.currentController?.action;
            if (
                currentAction?.kiosk_enabled &&
                currentAction.kiosk_refresh_mode === "realtime" &&
                payload?.model === currentAction.res_model
            ) {
                scheduleReload(currentAction);
            }
        });
        // Bus reconnected (e.g. after a worker restart): a message could
        // have been missed while offline, so refresh defensively.
        bus_service.addEventListener("reconnect", () => {
            const currentAction = action.currentController?.action;
            if (currentAction?.kiosk_enabled && currentAction.kiosk_refresh_mode === "realtime") {
                scheduleReload(currentAction);
            }
        });

        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => {
            clearTimers();
            const currentAction = action.currentController?.action;
            document.body.classList.toggle(KIOSK_BODY_CLASS, Boolean(currentAction?.kiosk_enabled));

            if (!currentAction?.kiosk_enabled) {
                unsubscribeModel();
                return;
            }
            if (currentAction.kiosk_refresh_mode === "interval") {
                unsubscribeModel();
                const seconds = currentAction.kiosk_refresh_interval || 30;
                refreshTimer = browser.setInterval(() => reload(currentAction), seconds * 1000);
            } else if (currentAction.kiosk_refresh_mode === "realtime") {
                if (subscribedModel !== currentAction.res_model) {
                    unsubscribeModel();
                    subscribedModel = currentAction.res_model;
                    bus_service.addChannel(`kiosk_refresh-${subscribedModel}`);
                }
                safetyTimer = browser.setInterval(
                    () => reload(currentAction),
                    KIOSK_SAFETY_INTERVAL_MS
                );
            }
        });
    },
};

registry.category("services").add("kiosk_chrome", kioskChromeService);
