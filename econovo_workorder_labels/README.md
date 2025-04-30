# README for Econovo Workorder Labels

## Overview

The `econovo_workorder_labels` module is designed to facilitate the printing of labels for work orders in Odoo. These labels are formatted to display essential information about each work order, making it easier for users to manage and track production processes.

## Features

- Print labels for work orders with the following information:
  - Production Date
  - Display Name
  - Production ID
  - Product ID
  - Needed By Work Order IDs
  - Blocked By Work Order IDs
  - Quantity Produced
  - Parent and Ancestor of the Product

## Installation

To install the `econovo_workorder_labels` module, follow these steps:

1. Place the module folder in your Odoo addons directory.
2. Update the app list in Odoo.
3. Search for "Econovo Workorder Labels" in the apps menu.
4. Click on the install button.

## Usage

Once installed, the module will allow users to generate and print labels for work orders directly from the Odoo interface. Users can access the label printing functionality through the relevant work order views.

## Dependencies

This module depends on the following Odoo modules:
- `mrp` (Manufacturing)

## Author

Jose D. Leonett

## License

AGPL-3

## Website

[http://josedleonett.github.com](http://josedleonett.github.com)