"""
Runtime patches for third-party SoloPy interfaces used in the VACOP project.

SoloPy 4.1.0 may return three values from `Mcp2515.canopen_transmit` when no
response is received, whereas the higher level API expects exactly two
elements. This helper trims the tuple to two entries so upstream code does not
crash with `ValueError: too many values to unpack`.
"""

from __future__ import annotations


def patch_solopy_mcp2515() -> bool:
    """Ensure canopen_transmit from SoloPy's MCP2515 driver always returns 2 values."""
    try:
        from SoloPy.Mcp2515 import Mcp2515  # type: ignore
        from SoloPy.SOLOMotorControllers import Error  # type: ignore
    except Exception:
        # SoloPy not installed; nothing to patch.
        return False

    if getattr(Mcp2515, "_vacop_canopen_patched", False):
        return True

    original_canopen_transmit = Mcp2515.canopen_transmit

    def safe_canopen_transmit(self, *args, **kwargs):
        result = original_canopen_transmit(self, *args, **kwargs)
        if isinstance(result, tuple):
            if len(result) == 2:
                return result
            if len(result) >= 2:
                return result[0], result[1]
        return result, Error.GENERAL_ERROR

    Mcp2515.canopen_transmit = safe_canopen_transmit
    Mcp2515._vacop_canopen_patched = True
    return True

