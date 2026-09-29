"""Single-frame playblasts from multiple cameras in a shot."""

# Defined before the import below, so ui and capture can read it back off the
# package while the package is still being imported.
__version__ = "2.0.1"

from .ui import show

__all__ = ["show", "__version__"]
