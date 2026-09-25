"""
Projection engine (gaspatchio).

Shared by every basis: the grid, curves, gaspatchio assumption tables, the
product models (``projections/``), the seriatim dispatcher, the reinsurance-
ready :class:`~actuarial_model.engine.projection.Projection` carrier, and
the per-policy aggregation. Bases (``actuarial_model.bases``) consume
projections; they never project on their own.
"""

from loguru import logger

# gaspatchio logs every table registration / dispatch at DEBUG through loguru;
# keep AKIRA's output to its own ``logging`` configuration.
logger.disable("gaspatchio")
