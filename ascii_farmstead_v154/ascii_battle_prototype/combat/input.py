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
                numpad_scan = {
                    "G": "NUM7", "I": "NUM9", "L": "NUM5",
                    "O": "NUM1", "Q": "NUM3",
                }
                if code in numpad_scan:
                    return numpad_scan[code]
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
            return f"NUM{ch}" if ch.isdigit() else ch.lower()

        ch = sys.stdin.read(1)
        if ch == "\x1b":
            n1 = sys.stdin.read(1)
            if n1 == "[":
                n2 = sys.stdin.read(1)
                return {
                    "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
                    "H": "NUM7", "F": "NUM1",
                }.get(n2, "ESC")
            if n1 == "O":
                n2 = sys.stdin.read(1)
                return {
                    "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
                    "q": "NUM1", "r": "NUM2", "s": "NUM3", "t": "NUM4",
                    "u": "NUM5", "v": "NUM6", "w": "NUM7", "x": "NUM8", "y": "NUM9",
                }.get(n2, "ESC")
            return "ESC"
        if ch == "\n":
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch in ("\b", "\x7f"):
            return "BACKSPACE"
        if ch == "\t":
            return "TAB"
        return f"NUM{ch}" if ch.isdigit() else ch.lower()


# ---------------------------------------------------------------------------
# Core data
# ---------------------------------------------------------------------------

