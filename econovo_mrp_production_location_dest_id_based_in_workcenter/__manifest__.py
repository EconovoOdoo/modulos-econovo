{
    'name': 'Econovo MRP Production Location Dest ID Based in Workcenter',
    'version': '17.0.1.1.0',
    'category': 'Manufacturing',
    'summary': 'Set destination location for finished products at workcenter level',
    'description': """
Econovo MRP Production Location Dest ID Based in Workcenter
===========================================================

This module extends the manufacturing functionality to allow setting 
destination locations for finished products at the workcenter level
instead of just at the production order level.

Features:
---------
* Add destination location field to workcenters
* Override production location computation to use workcenter-specific destinations
* Uses LAST workcenter with destination configured (makes manufacturing sense)
* Fallback to default behavior when no workcenter destination is set
* Support for multi-step manufacturing routing

Use Case:
---------
When you have different workcenters that produce finished goods that should
be stored in different locations, you can now configure each workcenter with
its preferred destination location. The system uses the LAST workcenter with
destination configured as the final operation determines the final storage location.

Configuration:
--------------
1. Go to Manufacturing > Configuration > Work Centers
2. Open a work center and set the "Destination Location"
3. Create manufacturing orders that use routing with this work center
4. Finished products will be moved to the LAST workcenter's destination location
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_workcenter_views.xml',
        'views/mrp_production_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
