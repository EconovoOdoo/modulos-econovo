/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { translatedTerms } from "@web/core/l10n/translation";
import { session } from "@web/session";

const roomTranslationService = {
    dependencies: ["localization"],
    async start() {
        const cacheHashes = session.cache_hashes || {};
        const translationsHash = cacheHashes.translations || Date.now().toString();
        const lang = document.documentElement.lang?.replace(/-/g, "_");
        let url = `/web/webclient/translations/${translationsHash}?mods=room`;
        if (lang) {
            url += `&lang=${lang}`;
        }

        const response = await browser.fetch(url);
        if (!response.ok) {
            return;
        }
        const { modules } = await response.json();
        for (const message of modules.room?.messages || []) {
            translatedTerms[message.id] = message.string;
        }
    },
};

registry.category("services").add("room_translation", roomTranslationService);