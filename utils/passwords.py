import re

_MIN_LEN = 8


def password_errors(password: str | None) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    if not password:
        return ["Password is required."]
    if len(password) < _MIN_LEN:
        return [f"Password must be at least {_MIN_LEN} characters."]
    if not re.search(r"[A-Za-z]", password):
        return ["Password must include at least one letter."]
    if not re.search(r"\d", password):
        return ["Password must include at least one number."]
    return []
