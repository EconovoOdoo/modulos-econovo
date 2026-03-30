# -*- coding: utf-8 -*-

from . import models
from .hooks import migrate_studio_fields


def _post_init_hook(env):
    migrate_studio_fields(env)
