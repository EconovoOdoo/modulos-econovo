/** @odoo-module **/

/**
 * Patch DomainSelector to expose =ilike (and its negation) as selectable
 * operators in the "Add custom filter" dialog for char / text / html fields.
 *
 * Odoo 17 includes =ilike at the server level (expression.py) and even has
 * a label for it in tree_editor_operator_editor.js, but getDomainDisplayedOperators
 * only lists "ilike" / "not ilike" for text fields, hiding =ilike from the UI.
 *
 * After this patch the operator dropdown for text fields becomes:
 *   =  |  !=  |  contains  |  starts / ends with (use %)
 *                           |  does not start / end with (use %)
 *              |  does not contain  |  is in  |  is not in  |  is set  |  is not set
 */

import { patch } from "@web/core/utils/patch";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { getDomainDisplayedOperators } from "@web/core/domain_selector/domain_selector_operator_editor";
import { getOperatorEditorInfo } from "@web/core/tree_editor/tree_editor_operator_editor";
import { formatValue } from "@web/core/tree_editor/condition_tree";
import { _t } from "@web/core/l10n/translation";

/** Field types that benefit from the =ilike operator. */
const TEXT_FIELD_TYPES = new Set(["char", "text", "html"]);

/**
 * Key used by tree_editor_operator_editor internals for (=ilike, negate=true).
 *
 * toKey("=ilike", true) = JSON.stringify([formatValue("=ilike"), true])
 * formatValue("=ilike") returns the Python string repr: '"=ilike"'
 * so the resulting key is ["\"=ilike\"", true] serialised as JSON.
 */
const NEGATED_ILIKE_KEY = JSON.stringify([formatValue("=ilike"), true]);

/** Save the original method so we can delegate non-text fields unchanged. */
const _origGetOperatorEditorInfo = DomainSelector.prototype.getOperatorEditorInfo;

patch(DomainSelector.prototype, {
    /**
     * For char / text / html fields: insert the =ilike operator (and its
     * negation) right after "ilike" in the dropdown, with user-friendly labels.
     * For every other field type the original behaviour is preserved.
     *
     * @param {Object} node  – condition tree node (has .path, .operator, .negate)
     * @returns {Object}     – operator editor info consumed by TreeEditor
     */
    getOperatorEditorInfo(node) {
        const fieldDef = this.getFieldDef(node.path);

        // Non-text fields: fall back to the standard implementation unchanged.
        if (!fieldDef || !TEXT_FIELD_TYPES.has(fieldDef.type)) {
            return _origGetOperatorEditorInfo.call(this, node);
        }

        // ---- base operators for this text field --------------------------------
        // getDomainDisplayedOperators returns:
        //   ["=", "!=", "ilike", "not ilike", "in", "not in", "set", "not_set"]
        const baseOperators = getDomainDisplayedOperators(fieldDef);

        // Insert "=ilike" immediately after "ilike".
        const extendedOperators = [];
        for (const op of baseOperators) {
            extendedOperators.push(op);
            if (op === "ilike") {
                extendedOperators.push("=ilike");
            }
        }

        // Build the standard editor info using the extended operator list.
        // getOperatorEditorInfo returns a Select-based component descriptor where
        //   options = [[key, label], ...]  and  update(key) drives domain changes.
        const stdInfo = getOperatorEditorInfo(extendedOperators);

        return {
            ...stdInfo,
            extractProps: ({ update, value: [operator, negate] }) => {
                // Delegate to the standard extractProps to get the current key,
                // options list, and update callback — then we augment the labels.
                const stdProps = stdInfo.extractProps({ update, value: [operator, negate] });

                // --- Build the final options array --------------------------------
                // 1. Remove NEGATED_ILIKE_KEY from wherever stdInfo may have placed
                //    it (it adds it at the end as a fallback when the current value
                //    matches it but the key is not in the pre-built list).
                const options = stdProps.options
                    .filter(([k]) => k !== NEGATED_ILIKE_KEY)
                    .map(([key, label]) => {
                        // Replace the technical "=ilike" label with a friendly one.
                        if (key === "=ilike") {
                            return [key, _t("empieza / termina con (usar %)")];
                        }
                        return [key, label];
                    });

                // 2. Always insert the negated =ilike right after =ilike.
                const ilikeIdx = options.findIndex(([k]) => k === "=ilike");
                if (ilikeIdx !== -1) {
                    options.splice(ilikeIdx + 1, 0, [
                        NEGATED_ILIKE_KEY,
                        _t("no empieza / termina con (usar %)"),
                    ]);
                }

                return { ...stdProps, options };
            },
        };
    },
});
