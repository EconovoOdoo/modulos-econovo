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
// Independent of kiosk_refresh_mode/kiosk_refresh_interval: always
// re-checks the live kiosk_enabled/mode on this fixed, short cadence.
// This is deliberately NOT tied to ACTION_MANAGER:UI-UPDATED alone,
// because that event only fires on navigation/doAction - disabling
// Kiosk Mode on the action record does not by itself trigger anything
// (only writes on the model the action *watches* notify the bus, see
// ir_actions_act_window.py `_kiosk_notify`). Without this poll, a
// long-lived idle kiosk screen could keep applying kiosk chrome/refresh
// for as long as its data-refresh cadence (up to the 5 min safety net
// in realtime mode) after being turned off.
const KIOSK_STATE_POLL_MS = 10 * 1000;

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
    dependencies: ["action", "bus_service", "orm", "mail.sound_effects"],
    start(env, { action, bus_service, orm, "mail.sound_effects": soundEffects }) {
        let refreshTimer = null;
        let safetyTimer = null;
        let debounceTimer = null;
        let pollTimer = null;
        let subscribedModel = null;
        let updateToken = 0;
        // Whether the currently displayed action wants a sound played on
        // genuine bus-triggered refreshes (kiosk_sound_alert); kept in
        // sync by applyState(), read by the bus subscription below.
        let soundAlertEnabled = false;
        // Signature of the last APPLIED kiosk config, used to avoid
        // tearing down and recreating the data-refresh timer/bus
        // subscription on every poll tick when nothing actually changed
        // (that would otherwise prevent e.g. a 30s interval from ever
        // completing a cycle, since the poll runs every 10s).
        let lastSignature = null;

        const clearDataTimers = () => {
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
            clearDataTimers();
            unsubscribeModel();
            browser.clearInterval(pollTimer);
            pollTimer = null;
            lastSignature = null;
            soundAlertEnabled = false;
            kioskState.actionId = null;
            kioskState.hideChat = false;
            document.body.classList.remove(KIOSK_BODY_CLASS);
        };

        const reload = (actionId, { withSound = false } = {}) => {
            debounceTimer = null;
            // Only reload if that action is still the one on screen.
            if (action.currentController?.action?.id === actionId) {
                if (withSound) {
                    // Reuses Discuss' own notification sound - no new
                    // audio asset needed. Autoplay may be silently
                    // blocked by the browser if the kiosk tab never had
                    // a user gesture; that's a launcher/deployment
                    // concern (see README), not something to handle here.
                    soundEffects.play("new-message");
                }
                action.doAction(actionId, { clearBreadcrumbs: true });
            }
        };

        const scheduleReload = (actionId, options) => {
            if (!debounceTimer) {
                debounceTimer = browser.setTimeout(() => reload(actionId, options), KIOSK_REFRESH_DEBOUNCE_MS);
            }
        };

        // Custom notification type sent by `ir.actions.act_window._kiosk_notify`.
        bus_service.subscribe("kiosk_refresh", (payload) => {
            if (
                kioskState.actionId &&
                subscribedModel &&
                payload?.model === subscribedModel &&
                action.currentController?.action?.id === kioskState.actionId
            ) {
                scheduleReload(kioskState.actionId, { withSound: soundAlertEnabled });
            }
        });
        // Bus reconnected (e.g. after a worker restart): a message could
        // have been missed while offline, so refresh defensively. No
        // sound here - a reconnect is not evidence that anything new
        // actually happened, only genuine kiosk_refresh signals are.
        bus_service.addEventListener("reconnect", () => {
            if (subscribedModel && kioskState.actionId) {
                scheduleReload(kioskState.actionId);
            }
        });

        /** Apply a freshly-read kiosk state; cheap parts (body class,
         * kioskState) always run, but the data-refresh timers/bus
         * subscription are only rebuilt when the relevant config
         * actually changed since the last check. */
        const applyState = (actionId, resModel, fresh) => {
            const enabled = Boolean(fresh?.kiosk_enabled);
            kioskState.actionId = actionId;
            kioskState.hideChat = Boolean(enabled && fresh?.kiosk_hide_chat_window);
            soundAlertEnabled = Boolean(
                enabled && fresh?.kiosk_refresh_mode === "realtime" && fresh?.kiosk_sound_alert
            );
            document.body.classList.toggle(KIOSK_BODY_CLASS, enabled);

            const signature = JSON.stringify({
                actionId,
                resModel,
                enabled,
                refreshMode: fresh?.kiosk_refresh_mode,
                refreshInterval: fresh?.kiosk_refresh_interval,
            });
            if (signature === lastSignature) {
                return;
            }
            lastSignature = signature;

            clearDataTimers();
            if (!enabled) {
                unsubscribeModel();
                return;
            }
            if (fresh.kiosk_refresh_mode === "interval") {
                unsubscribeModel();
                const seconds = fresh.kiosk_refresh_interval || 30;
                refreshTimer = browser.setInterval(() => reload(actionId), seconds * 1000);
            } else if (fresh.kiosk_refresh_mode === "realtime") {
                if (subscribedModel !== resModel) {
                    unsubscribeModel();
                    subscribedModel = resModel;
                    bus_service.addChannel(`kiosk_refresh-${subscribedModel}`);
                }
                safetyTimer = browser.setInterval(() => reload(actionId), KIOSK_SAFETY_INTERVAL_MS);
            } else {
                unsubscribeModel();
            }
        };

        const checkNow = () => {
            const token = ++updateToken;
            const currentAction = action.currentController?.action;

            if (currentAction?.type !== "ir.actions.act_window" || !currentAction.id) {
                reset();
                return;
            }

            orm.call("ir.actions.act_window", "get_kiosk_state", [currentAction.id])
                .then((fresh) => {
                    if (token !== updateToken) {
                        return; // superseded by a newer check, ignore
                    }
                    applyState(currentAction.id, currentAction.res_model, fresh);
                })
                .catch(() => {
                    // Fail safe: if we can't confirm the kiosk state (e.g.
                    // the record was deleted, or a transient RPC error),
                    // never get stuck applying kiosk chrome/refresh.
                    if (token === updateToken) {
                        reset();
                    }
                });
        };

        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => {
            browser.clearInterval(pollTimer);
            const currentAction = action.currentController?.action;
            pollTimer =
                currentAction?.type === "ir.actions.act_window" && currentAction.id
                    ? browser.setInterval(checkNow, KIOSK_STATE_POLL_MS)
                    : null;
            checkNow();
        });
    },
};

registry.category("services").add("kiosk_chrome", kioskChromeService);


