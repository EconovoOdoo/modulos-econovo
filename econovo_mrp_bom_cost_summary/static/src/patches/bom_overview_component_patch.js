/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BomOverviewComponent } from
    "@mrp/components/bom_overview/mrp_bom_overview";

patch(BomOverviewComponent.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            costSummary: false,
            secondaryCurrency: false,
        });
    },

    async getBomData() {
        const bomData = await super.getBomData(...arguments);
        this.state.secondaryCurrency = bomData.secondary_currency || false;
        this.state.costSummary = this._computeCostSummary(
            this.state.bomData,
            this.state.secondaryCurrency
        );
        return bomData;
    },

    /**
     * Traverses the recursive bomData tree and aggregates:
     * - Component costs by category -> product -> parent usages (3-level)
     * - Operation costs by work center with inline parent reference
     *
     * @param {Object} data - The recursive BOM data tree (state.bomData)
     * @param {Object|false} secondaryCurrency - USD currency info or false
     * @returns {Object|false} Cost summary object or false if empty
     */
    _computeCostSummary(data, secondaryCurrency) {
        const categoryMap = {};
        const workcenterMap = {};
        this._collectCosts(data, categoryMap, workcenterMap);

        const rate = secondaryCurrency ? secondaryCurrency.rate : 0;

        // Convert categoryMap products from nested maps to sorted arrays
        const categories = Object.values(categoryMap)
            .map((cat) => {
                const products = Object.values(cat.products)
                    .sort((a, b) => b.total - a.total);
                return { ...cat, products };
            })
            .sort((a, b) => b.total - a.total);
        const workcenters = Object.values(workcenterMap).sort(
            (a, b) => b.total - a.total
        );

        if (categories.length === 0 && workcenters.length === 0) {
            return false;
        }

        const totalComponents = categories.reduce((s, c) => s + c.total, 0);
        const totalOperations = workcenters.reduce((s, w) => s + w.total, 0);
        const totalBom = totalComponents + totalOperations;

        // Compute percentages and USD for categories -> products -> usages
        for (const cat of categories) {
            cat.percentage = totalComponents
                ? (cat.total / totalComponents) * 100
                : 0;
            cat.total_usd = rate ? cat.total * rate : false;
            for (const prod of cat.products) {
                prod.total_usd = rate ? prod.total * rate : false;
                for (const usage of prod.usages) {
                    usage.total_usd = rate ? usage.total * rate : false;
                }
            }
        }
        // Compute percentages and USD for workcenters -> items
        for (const wc of workcenters) {
            wc.percentage = totalOperations
                ? (wc.total / totalOperations) * 100
                : 0;
            wc.total_usd = rate ? wc.total * rate : false;
            for (const item of wc.items) {
                item.total_usd = rate ? item.total * rate : false;
            }
        }

        return {
            categories,
            workcenters,
            totals: {
                components: totalComponents,
                components_usd: rate ? totalComponents * rate : false,
                operations: totalOperations,
                operations_usd: rate ? totalOperations * rate : false,
                total: totalBom,
                total_usd: rate ? totalBom * rate : false,
            },
            currency_id: data.currency_id,
        };
    },

    /**
     * Recursively walks the BOM tree collecting leaf component and
     * operation costs, tracking parent product for traceability.
     *
     * @param {Object} node - Current BOM tree node
     * @param {Object} categoryMap - Accumulator for category groupings
     * @param {Object} workcenterMap - Accumulator for workcenter groupings
     * @param {number} [ancestorCostShare=1.0] - Accumulated cost_share
     *   factor from ancestor BOM nodes (for byproduct cost adjustments)
     */
    _collectCosts(node, categoryMap, workcenterMap, ancestorCostShare = 1.0) {
        // The current node IS the product being manufactured.
        // Its components and operations belong to this parent.
        const parentName = node.name;
        const parentProductId = node.product_id;

        // When a BOM has byproducts, Odoo multiplies the node total by
        // cost_share (< 1.0).  We must apply the same factor to every
        // leaf cost we collect so the summary matches the BOM total.
        const nodeCostShare =
            node.cost_share !== undefined && node.cost_share !== null
                ? node.cost_share
                : 1.0;
        const effectiveCostShare = ancestorCostShare * nodeCostShare;

        // Collect operations at this BOM level (with parent context inline)
        if (node.operations) {
            for (const op of node.operations) {
                const wcId = op.workcenter_id || 0;
                const wcName = op.workcenter_name || _t("Unknown");
                if (!workcenterMap[wcId]) {
                    workcenterMap[wcId] = {
                        id: wcId,
                        name: wcName,
                        total: 0,
                        items: [],
                    };
                }
                const adjustedCost = (op.bom_cost || 0) * effectiveCostShare;
                workcenterMap[wcId].total += adjustedCost;
                workcenterMap[wcId].items.push({
                    name: op.operation_name || op.name,
                    duration: op.quantity,
                    total: adjustedCost,
                    parent_name: parentName,
                    parent_product_id: parentProductId,
                });
            }
        }

        // Process components
        if (node.components) {
            for (const comp of node.components) {
                if (comp.type === "bom" && comp.components) {
                    // Sub-BOM: recurse — the child's own cost_share will
                    // be applied on the next level of recursion.
                    this._collectCosts(
                        comp, categoryMap, workcenterMap, effectiveCostShare
                    );
                } else {
                    // Leaf component: add to category -> product -> usages
                    const catId = comp.categ_id || 0;
                    const catName = comp.categ_name || _t("Uncategorized");
                    if (!categoryMap[catId]) {
                        categoryMap[catId] = {
                            id: catId,
                            name: catName,
                            total: 0,
                            products: {},
                        };
                    }
                    const adjustedCost =
                        (comp.bom_cost || 0) * effectiveCostShare;
                    const cat = categoryMap[catId];
                    cat.total += adjustedCost;

                    // Group by product within category
                    const prodId = comp.product_id;
                    if (!cat.products[prodId]) {
                        cat.products[prodId] = {
                            product_id: prodId,
                            name: comp.name,
                            total: 0,
                            usages: [],
                        };
                    }
                    const product = cat.products[prodId];
                    product.total += adjustedCost;

                    // Aggregate usages by parent product
                    // (same component may appear multiple times in same parent)
                    const existingUsage = product.usages.find(
                        (u) => u.parent_product_id === parentProductId
                    );
                    if (existingUsage) {
                        existingUsage.quantity += comp.quantity || 0;
                        existingUsage.total += adjustedCost;
                    } else {
                        product.usages.push({
                            parent_product_id: parentProductId,
                            parent_name: parentName,
                            quantity: comp.quantity || 0,
                            uom_name: comp.uom_name,
                            total: adjustedCost,
                        });
                    }
                }
            }
        }
    },
});
