"""Shared terminal colors; presentation only, with no third-party dependencies."""
import os
import sys

COLORS = {'input': '\033[38;2;57;255;20m', 'data': '\033[97m',
          'reply': '\033[38;2;255;128;191m', 'meta': '\033[96m',
          'muted': '\033[90m', 'warning': '\033[93m', 'error': '\033[91m',
          'reset': '\033[0m'}


def enabled():
    return sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'


def paint(text, kind, colored):
    return COLORS[kind] + text + COLORS['reset'] if colored else text


def safe(text):
    """Show message controls literally; allow only readable newlines and tabs."""
    return ''.join(f'\\x{ord(c):02x}' if (ord(c) < 32 and c not in '\n\t')
                   or 127 <= ord(c) < 160 else c for c in str(text))
