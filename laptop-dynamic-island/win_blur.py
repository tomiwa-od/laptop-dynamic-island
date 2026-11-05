"""
Optional Windows acrylic / blur-behind for a window, via ctypes.

Best-effort and fully guarded: if the (undocumented) API isn't present it just
returns False and changes nothing, so the island keeps its normal look.
"""

import ctypes
from ctypes import wintypes

ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19


class _ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),   # 0xAABBGGRR
        ("AnimationId", ctypes.c_uint),
    ]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _apply(hwnd, state, gradient_color):
    try:
        accent = _ACCENTPOLICY()
        accent.AccentState = state
        accent.AccentFlags = 0
        accent.GradientColor = gradient_color
        data = _WINCOMPATTRDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        fn = ctypes.windll.user32.SetWindowCompositionAttribute
        fn.argtypes = [wintypes.HWND, ctypes.POINTER(_WINCOMPATTRDATA)]
        fn(wintypes.HWND(int(hwnd)), ctypes.byref(data))
        return True
    except Exception:
        return False


def enable_blur(hwnd, acrylic=True, gradient_color=0x40101014):
    """Frost the window so the wallpaper/content behind it shows through blurred."""
    state = ACCENT_ENABLE_ACRYLICBLURBEHIND if acrylic else ACCENT_ENABLE_BLURBEHIND
    return _apply(hwnd, state, gradient_color)


def disable_blur(hwnd):
    return _apply(hwnd, ACCENT_DISABLED, 0)
