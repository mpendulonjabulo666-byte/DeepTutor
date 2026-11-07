"""Exact, checked diagrams drawn by code. See ``templates.REGISTRY``."""

from .core import Canvas, DiagramError
from .templates import REGISTRY, Template, catalogue, render

__all__ = ["Canvas", "DiagramError", "REGISTRY", "Template", "catalogue", "render"]
