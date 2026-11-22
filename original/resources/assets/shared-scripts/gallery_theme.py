"""Fixed categorical order C and unchanged continuous base order P."""
from matplotlib.colors import to_rgb, to_hex
try:
    from .vivid_config import palette_colors, categorical_colors
    from .palette_maps import palette_cmap, palette_stops
except ImportError:
    from vivid_config import palette_colors, categorical_colors
    from palette_maps import palette_cmap, palette_stops

P = palette_colors()
C = categorical_colors()
P = (P * 8)[:max(8, len(P))]
C = (C * 8)[:max(8, len(C))]


def dark(color):
    return to_hex([v * 0.65 for v in to_rgb(color)])
