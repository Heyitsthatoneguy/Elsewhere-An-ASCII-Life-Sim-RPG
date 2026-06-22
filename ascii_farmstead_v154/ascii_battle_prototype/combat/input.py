from __future__ import annotations

import os
import sys

class KeyReader:
    def __enter__(self) -> "KeyReader":
        if os.name != "nt":
            import termios
            import tty
            self.termios = termios
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if os.name != "nt":
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old_settings)

    def read_key(self) -> str:
        if os.name == "nt":
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(code, "")
            if ch == "\r":
                return "ENTER"
            if ch == " ":
                return "SPACE"
            if ch in ("\b", "\x7f"):
                return "BACKSPACE"
            if ch == "\t":
                return "TAB"
            if ch == "\x1b":
                return "ESC"
            return ch.lower()

        ch = sys.stdin.read(1)
        if ch == "\x1b":
            n1 = sys.stdin.read(1)
            if n1 == "[":
                n2 = sys.stdin.read(1)
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(n2, "ESC")
            return "ESC"
        if ch == "\n":
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch in ("\b", "\x7f"):
            return "BACKSPACE"
        if ch == "\t":
            return "TAB"
        return ch.lower()


# ---------------------------------------------------------------------------
# Core data
# ---------------------------------------------------------------------------

