/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { BomOverviewDisplayFilter } from
    "@mrp/components/bom_overview_display_filter/mrp_bom_overview_display_filter";

// Extend props so OWL does not warn when 'performance' is passed in showOptions.
// mrp_plm (Enterprise) patches BomOverviewDisplayFilter.props.showOptions into a
// flat object (no 'shape' key), so we must handle both structures.
const _showOptions = BomOverviewDisplayFilter.props.showOptions;
if (_showOptions.shape) {
    _showOptions.shape.performance = Boolean;
} else {
    _showOptions.performance = Boolean;
}

patch(BomOverviewDisplayFilter.prototype, {
    setup() {
        super.setup(...arguments);
        // Add the 'performance' toggle to the dropdown after the standard options.
        this.displayOptions.performance = _t("Rendimiento de operaciones");
    },
});
