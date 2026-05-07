/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BomOverviewTable } from
    "@mrp/components/bom_overview_table/mrp_bom_overview_table";
import { BomOverviewLine } from
    "@mrp/components/bom_overview_line/mrp_bom_overview_line";
import { BomOverviewSpecialLine } from
    "@mrp/components/bom_overview_special_line/mrp_bom_overview_special_line";
import { BomCostSummarySection } from
    "../components/bom_cost_summary_section/bom_cost_summary_section";

// Extend showOptions.shape on all components that validate it, so OWL does not
// reject the 'performance' key added by bom_overview_component_patch.js.
function _extendShowOptions(component) {
    const so = component.props.showOptions;
    if (!so) { return; }
    if (so.shape) {
        so.shape.performance = { type: Boolean, optional: true };
    } else {
        so.performance = { type: Boolean, optional: true };
    }
}
_extendShowOptions(BomOverviewTable);
_extendShowOptions(BomOverviewLine);
_extendShowOptions(BomOverviewSpecialLine);

patch(BomOverviewTable, {
    components: {
        ...BomOverviewTable.components,
        BomCostSummarySection,
    },
    props: {
        ...BomOverviewTable.props,
        costSummary: { type: [Object, Boolean], optional: true },
        secondaryCurrency: { type: [Object, Boolean], optional: true },
    },
});
