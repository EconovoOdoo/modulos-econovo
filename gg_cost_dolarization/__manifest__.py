{
    "name": "Dolarizacion de Costos en reportes",
    "summary": "",
    "version": "17.0.1.0.0",
    "license": "AGPL-3",
    "author": "",
    "website": "",
    "depends": ["base", "product", "mrp", "mrp_bom_structure_xlsx"],
    "data": [
        'security/ir.model.access.csv',
    ],
    "assets": {
        "web.assets_backend": [
            "gg_cost_dolarization/static/src/**/*",
        ],
    },
    "demo": [],
    "installable": True,
}
