# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Saneen K (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    'name': "Product Multi UoM",
    'version': '17.0.1.2.0',
    'category': 'Sales & Purchases',
    'summary': 'Module to handle products with multiple UoM categories for sales and purchases',
    'description': (
        "This versatile module empowers your sales and purchase strategy by "
        "seamlessly handling products with diverse unit of measure categories. "
        "Whether you're selling or purchasing by length, weight, quantity, or more, "
        "this module ensures a streamlined and efficient process, allowing you to "
        "offer and manage your products with different UoM categories effortlessly."
    ),
    'author': 'Cybrosys Techno Solutions, J. Leonett',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'base',
        'sale_management',
        'purchase',
        'stock',
        'product'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_product_views.xml',
        'views/sale_order_line_views.xml',
        'views/purchase_order_line_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
