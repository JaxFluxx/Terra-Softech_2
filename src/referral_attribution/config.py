"""Configuration and portable project-path helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_project_root(start: Path | None = None) -> Path:
    """Find the repository root from the current folder or one of its parents."""
    current = (start or Path.cwd()).resolve()
    candidates = [current, *current.parents]

    for candidate in candidates:
        if (
            (candidate / "config" / "attribution_rules.json").exists()
            and (candidate / "data" / "raw").exists()
        ):
            return candidate

    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Could not locate the referral attribution project root. "
        "Run the command from the repository root or one of its subfolders.\n"
        f"Current working directory: {current}\n"
        f"Searched directories:\n{searched}"
    )


def load_rules(
    project_root: Path,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Load and minimally validate the business-rule configuration."""
    resolved_path = config_path or (
        project_root / "config" / "attribution_rules.json"
    )
    if not resolved_path.is_absolute():
        resolved_path = project_root / resolved_path
    resolved_path = resolved_path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Missing attribution configuration: {resolved_path}"
        )

    with resolved_path.open("r", encoding="utf-8") as handle:
        rules = json.load(handle)

    required_sections = {
        "identity",
        "time",
        "honored",
        "filters",
        "classification",
        "outputs",
    }
    missing = sorted(required_sections - set(rules or {}))
    if missing:
        raise ValueError(f"Configuration is missing required sections: {missing}")

    if rules["honored"]["primary_mode"] != "strict":
        raise ValueError("The accepted primary honored mode must remain 'strict'.")

    primary_route = rules["identity"].get("primary_route", {})
    if len(primary_route.get("booking_fields", [])) != len(
        primary_route.get("referral_fields", [])
    ) or not primary_route.get("booking_fields"):
        raise ValueError(
            "identity.primary_route must define matching booking_fields and "
            "referral_fields of the same non-zero length."
        )

    accepted_values = rules["honored"].get("strict", {}).get(
        "accepted_values", []
    )
    if not accepted_values:
        raise ValueError(
            "honored.strict.accepted_values must contain at least one source value."
        )

    priorities = rules["classification"].get("ops_priorities", {})
    expected_priorities = {
        "reverse_time",
        "primary_review",
        "secondary_review",
    }
    if set(priorities) != expected_priorities:
        raise ValueError(
            "classification.ops_priorities must define reverse_time, "
            "primary_review, and secondary_review."
        )

    return rules
