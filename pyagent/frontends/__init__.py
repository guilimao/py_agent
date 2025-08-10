# frontends/__init__.py
"""
前端模块初始化
"""

from .base import FrontendInterface
from .commandline import CommandlineFrontend

__all__ = ["FrontendInterface", "CommandlineFrontend"]