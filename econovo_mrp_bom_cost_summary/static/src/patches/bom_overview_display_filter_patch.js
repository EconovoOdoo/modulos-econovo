/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { BomOverviewDisplayFilter } from
    "@mrp/components/bom_overview_display_filter/mrp_bom_overview_display_filter";

// Extend props shape so OWL does not warn when 'performance' is passed
// in showOptions from BomCostSummaryView or the patched BomOverviewComponent.
BomOverviewDisplayFilter.props.showOptions.shape.performance = Boolean;

patch(BomOverviewDisplayFilter.prototype, {
    setup() {
        super.setup(...arguments);
        // Add the 'performance' toggle to the dropdown after the standard options.
        this.displayOptions.performance = _t("Rendimiento de operaciones");
    },
});
