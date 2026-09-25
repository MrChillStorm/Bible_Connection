"""Central font-size scaling. Every explicit font-size in the app is
computed by px(base) rather than a hardcoded literal, so the +/-
buttons above the reading pane can rescale everything at once instead
of only the base/inherited font (which a global stylesheet change
handles on its own -- see main_window.py's _refresh_all_fonts()).
Scale persists across launches via reading_state.get/set_font_scale()."""

MIN_SCALE = 0.75
MAX_SCALE = 1.75
SCALE_STEP = 0.1
DEFAULT_SCALE = 1.0

_scale = DEFAULT_SCALE


def get_scale() -> float:
    return _scale


def set_scale(value: float) -> float:
    global _scale
    _scale = round(max(MIN_SCALE, min(MAX_SCALE, value)), 2)
    return _scale


def px(base: int) -> int:
    """Scales a base pixel size (tuned at 100%) by the current font
    scale, e.g. px(14) -> 14 at 100%, 17 at 120%."""
    return round(base * _scale)
