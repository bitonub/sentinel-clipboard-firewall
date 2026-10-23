"""Shared input budget, independent of interfaces and I/O."""

MAX_INPUT_BYTES = 1024 * 1024


class InputError(ValueError):
    """A static diagnostic safe for presentation to the user."""


def utf8_size(text: str) -> int:
    """Validate without allocating an unbounded encoded copy."""
    size = 0
    try:
        for offset in range(0, len(text), 4096):
            size += len(text[offset:offset + 4096].encode("utf-8"))
            if size > MAX_INPUT_BYTES:
                raise InputError("La entrada supera 1 MiB UTF-8.")
    except UnicodeEncodeError:
        raise InputError("La entrada no es UTF-8 válido.") from None
    return size
