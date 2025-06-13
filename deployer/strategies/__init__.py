# deployer/strategies/__init__.py
"""
Módulo de estratégias de trading.
"""

from .entries import pattern_rsi_trend, bb_trend

__all__ = ["pattern_rsi_trend", "bb_trend"]