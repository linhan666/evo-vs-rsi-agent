"""Frozen search space and the per-ticket budget that bounds it.

Kept free of imports on purpose: `python -m evovs_science.search.space` would
otherwise find the submodule already imported by the package and warn.
Import the pieces explicitly (`from evovs_science.search.space import get`).
"""
