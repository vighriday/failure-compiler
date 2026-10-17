"""Display helpers. Labels never participate in scheduling or identity."""

import re


def route_label(name: str) -> str:
    return name if re.match(r"^route\s", name, re.IGNORECASE) else f"Route {name}"


def route_letters(names: list[str]) -> str:
    return ", ".join(re.sub(r"^route\s+", "", name, flags=re.IGNORECASE) for name in names)
