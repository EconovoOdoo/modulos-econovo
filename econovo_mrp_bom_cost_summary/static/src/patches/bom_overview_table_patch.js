/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BomOverviewTable } from
    "@mrp/components/bom_overview_table/mrp_bom_overview_table";
import { BomCostSummarySection } from
    "../components/bom_cost_summary_section/bom_cost_summary_section";

// Register sub-component and extend accepted props
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
