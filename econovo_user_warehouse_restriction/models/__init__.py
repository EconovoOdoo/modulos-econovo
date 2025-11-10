# -*- coding: utf-8 -*-
# This module extends user_warehouse_restriction via security rules and
# removes the restrictive validation that prevents administrators from
# configuring warehouse access properly.
from . import stock_warehouse
from . import stock_location
from . import res_users
from . import stock_move
