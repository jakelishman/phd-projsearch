"""Project to find some perfect projectors mapping a target state purely into
the excited state, and the rest of an orthonormal basis set onto purely the
ground state.  This is for better measurement in an ion trap than just "undoing"
the pulse sequence that was used to build the target state."""

from . import run
from . import parse
from .run import *

__all__ = run.__all__
