# -*- coding: utf-8 -*-
from . import models
from . import report


def post_init_hook(env):
    from .hooks import setup_svt04_worksheet
    setup_svt04_worksheet(env)
