"""Bounded library of parametric part templates. Importing this package registers all of them."""

from .base import Param, Template, all_templates, get, register  # noqa: F401
from . import box, cable_comb, l_bracket, shelf_bracket, standoff_mount, vase  # noqa: F401
