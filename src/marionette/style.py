"""Shared terminal colors; presentation only, with no third-party dependencies."""
import os
import sys

PALETTE = {
    'input': '#39FF14', 'data': '#FFFFFF', 'meta': '#55E7FF',
    'ids': '#C6B4FF', 'muted': '#8ACBFF', 'thinking_heading': '#FFE66D',
    'answer_heading': '#FF9ACB', 'reply': '#FF4FA3', 'success': '#5CFFD6',
    'timing': '#FFC49B', 'tokens': '#D69CFF', 'warning': '#FFAD55', 'error': '#FF6262',
}
COLORS = {name: '\033[38;2;' + ';'.join(str(int(value[i:i+2], 16)) for i in (1, 3, 5)) + 'm'
          for name, value in PALETTE.items()}
COLORS['reset'] = '\033[0m'


def enabled():
    return sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'


def paint(text, kind, colored):
    return COLORS[kind] + text + COLORS['reset'] if colored else text


def safe(text):
    """Show message controls literally; allow only readable newlines and tabs."""
    return ''.join(f'\\x{ord(c):02x}' if (ord(c) < 32 and c not in '\n\t')
                   or 127 <= ord(c) < 160 else c for c in str(text))
