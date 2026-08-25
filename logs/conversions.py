"""Glucose unit conversion, in one place.

Glucose is stored in mmol/L and converted to mg/dL only at the edges, driven by
the user's `UserPreferences.glucose_unit`. Both `logs` and `dashboard` render
readings, so the factor lived in both and was additionally hard-coded at the one
site that mattered most. It lives here now.
"""

from decimal import Decimal

# Standard conversion factor between mmol/L and mg/dL. Deliberately an int: the
# display path multiplies floats by it, and the storage path wraps it in
# Decimal(). Making it a Decimal would break the former with a TypeError.
MMOL_TO_MGDL = 18

# The precision at which mmol/L is stored. Must match GlucoseLog.value's
# decimal_places — see the round-trip test in logs/tests.py, which fails if
# these drift apart.
#
# The two units share no exact grid, so every mg/dL entry is quantised on the
# way in and multiplied back out on the way to the page. Three decimal places is
# the point at which that becomes lossless: across the accepted 20-700 mg/dL
# range, every whole value redisplays as itself. At two places, 44% of them come
# back up to 0.1 mg/dL off (100 -> 100.1); at one place, 89% do, by as much as
# 0.8 (100 -> 100.8).
MMOL_QUANTUM = Decimal("0.001")


def mgdl_to_mmol(value):
    """Convert a mg/dL reading to the mmol/L value to store."""
    return (value / Decimal(MMOL_TO_MGDL)).quantize(MMOL_QUANTUM)
