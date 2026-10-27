"""Small typed helpers for untrusted provider JSON."""

type Json = None | bool | int | float | str | list[Json] | dict[str, Json]


def object_value(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise ValueError("Invalid provider response")
    return value


def string_value(value: Json) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid provider response")
    return value


def list_value(value: Json) -> list[Json]:
    if not isinstance(value, list):
        raise ValueError("Invalid provider response")
    return value
