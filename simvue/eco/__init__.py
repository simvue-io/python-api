"""
Simvue Eco
==========

Contains functionality for green IT, monitoring emissions etc.
NOTE: The metrics calculated by these methods should be used for relative
comparisons only. Any values returned should not be taken as absolute.

"""

__date__ = "2025-03-06"

from .emissions_monitor import CO2Monitor as CO2Monitor

__all__ = ["CO2Monitor"]
