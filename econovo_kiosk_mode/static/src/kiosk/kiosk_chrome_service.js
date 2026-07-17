/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { kioskState } from "./kiosk_state";

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
 *
 * The kiosk fields are always re-read fresh via the `get_kiosk_state`
 * RPC instead of trusting `currentController.action.kiosk_enabled`: the
 * web client caches the loaded action dict per browser tab
 * (action_service.js `actionCache`), so that field can go stale after
 * the action record is edited - this is what previously caused a kiosk
 * screen to keep applying kiosk chrome/refresh even after
 * `kiosk_enabled` had been unchecked, until a full page reload.
 */
export const kioskChromeService = {
    dependencies: ["action", "bus_service", "orm"],
    start(env, { action, bus_service, orm }) {
        let refreshTimer = null;
        let safetyTimer = null;
        let debounceTimer = null;
        let subscribedModel = null;
        let updateToken = 0;
        // Local mirror of the freshly-read kiosk fields for whichever
        // action is on screen - only what this service needs to decide
        // on refresh. `kiosk_state.js` separately exposes only what
        // chat_window_patch.js needs.
        let live = { actionId: null, enabled: false, refreshMode: null };

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

        const reset = () => {
            clearTimers();
            unsubscribeModel();
            live = { actionId: null, enabled: false, refreshMode: null };
            kioskState.actionId = null;
            kioskState.hideChat = false;
            document.body.classList.remove(KIOSK_BODY_CLASS);
        };

        const reload = (actionId) => {
            debounceTimer = null;
            // Only reload if that action is still the one on screen.
            if (action.currentController?.action?.id === actionId) {
                action.doAction(actionId, { clearBreadcrumbs: true });
            }
        };

        const scheduleReload = (actionId) => {
            if (!debounceTimer) {
                debounceTimer = browser.setTimeout(() => reload(actionId), KIOSK_REFRESH_DEBOUNCE_MS);
            }
        };

        // Custom notification type sent by `ir.actions.act_window._kiosk_notify`.
        bus_service.subscribe("kiosk_refresh", (payload) => {
            const currentAction = action.currentController?.action;
            if (
                live.enabled &&
                live.refreshMode === "realtime" &&
                currentAction?.id === live.actionId &&
                payload?.model === currentAction.res_model
            ) {
                scheduleReload(live.actionId);
            }
        });
        // Bus reconnected (e.g. after a worker restart): a message could
        // have been missed while offline, so refresh defensively.
        bus_service.addEventListener("reconnect", () => {
            if (live.enabled && live.refreshMode === "realtime") {
                scheduleReload(live.actionId);
            }
        });

        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => {
            clearTimers();
            const token = ++updateToken;
            const currentAction = action.currentController?.action;

            if (currentAction?.type !== "ir.actions.act_window" || !currentAction.id) {
                reset();
                return;
            }

            orm.call("ir.actions.act_window", "get_kiosk_state", [currentAction.id])
                .then((fresh) => {
                    if (token !== updateToken) {
                        return; // superseded by a newer action change, ignore
                    }
                    live = {
                        actionId: currentAction.id,
                        enabled: Boolean(fresh?.kiosk_enabled),
                        refreshMode: fresh?.kiosk_refresh_mode,
                    };
                    kioskState.actionId = currentAction.id;
                    kioskState.hideChat = Boolean(live.enabled && fresh?.kiosk_hide_chat_window);

                    document.body.classList.toggle(KIOSK_BODY_CLASS, live.enabled);
                    if (!live.enabled) {
                        unsubscribeModel();
                        return;
                    }
                    if (live.refreshMode === "interval") {
                        unsubscribeModel();
                        const seconds = fresh?.kiosk_refresh_interval || 30;
                        refreshTimer = browser.setInterval(() => reload(currentAction.id), seconds * 1000);
                    } else if (live.refreshMode === "realtime") {
                        if (subscribedModel !== currentAction.res_model) {
                            unsubscribeModel();
                            subscribedModel = currentAction.res_model;
                            bus_service.addChannel(`kiosk_refresh-${subscribedModel}`);
                        }
                        safetyTimer = browser.setInterval(
                            () => reload(currentAction.id),
                            KIOSK_SAFETY_INTERVAL_MS
                        );
                    }
                })
                .catch(() => {
                    // Fail safe: if we can't confirm the kiosk state (e.g.
                    // the record was deleted, or a transient RPC error),
                    // never get stuck applying kiosk chrome/refresh.
                    if (token === updateToken) {
                        reset();
                    }
                });
        });
    },
};

registry.category("services").add("kiosk_chrome", kioskChromeService);

