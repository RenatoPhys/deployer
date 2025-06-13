# deployer/__init__.py
"""
Deployer - Sistema de deploy para trading algorítmico.

Um pacote Python para automatizar estratégias de trading com MetaTrader 5.
"""

__version__ = "0.1.0"
__author__ = "Renato"

from .trader import AlgoTrader
from .config.loader import ConfigManager, ConfigLoader

__all__ = ["AlgoTrader", "ConfigManager", "ConfigLoader"]