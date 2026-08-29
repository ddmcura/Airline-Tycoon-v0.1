"""Canonical Stage 1 Booking configuration construction and fingerprinting."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from .schema import (
    BOOKING_CONFIGURATION_FINGERPRINT_CONTRACT,
    DEFAULT_BOOKING_CONFIGURATION,
    DEFAULT_BOOKING_CHOICE_POLICY,
    LEGACY_BOOKING_CHOICE_POLICY,
)


def _configuration_from(value):
    if type(value) is not dict:
        raise ValueError("Booking configuration input must be a dictionary")
    if "simulation" in value:
        try:
            return value["simulation"]["configuration"]["booking"]
        except (KeyError, TypeError) as exc:
            raise ValueError("world has no Booking configuration") from exc
    return value


def calculate_booking_configuration_fingerprint(value):
    """Return the canonical witness over Booking configuration only."""
    configuration = _configuration_from(value)
    if type(configuration) is not dict:
        raise ValueError("Booking configuration must be a dictionary")
    try:
        material = {
            "fingerprint_contract": BOOKING_CONFIGURATION_FINGERPRINT_CONTRACT,
            "configuration": {
                key: configuration[key]
                for key in sorted(configuration)
                if key != "configuration_fingerprint"
            },
        }
        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(
            "Booking configuration inputs must be finite canonical JSON values"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def new_booking_configuration():
    """Return a detached approved V1 configuration with its integrity witness."""
    configuration = deepcopy(DEFAULT_BOOKING_CONFIGURATION)
    configuration["configuration_fingerprint"] = (
        calculate_booking_configuration_fingerprint(configuration)
    )
    return configuration


@dataclass(frozen=True)
class BookingConfigurationTransitionIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class BookingConfigurationTransitionResult:
    status: str
    previous_revision: int
    previous_fingerprint: str
    current_revision: int
    current_fingerprint: str
    changed: bool = False
    issues: tuple[BookingConfigurationTransitionIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _transition_rejection(configuration, code, message, path=None, *, status="REJECTED"):
    if type(configuration) is dict:
        revision = configuration.get("revision")
        fingerprint = configuration.get("configuration_fingerprint")
    else:
        revision = None
        fingerprint = None
    safe_revision = revision if type(revision) is int and revision >= 0 else 0
    safe_fingerprint = fingerprint if type(fingerprint) is str else ""
    return BookingConfigurationTransitionResult(
        status,
        safe_revision,
        safe_fingerprint,
        safe_revision,
        safe_fingerprint,
        issues=(BookingConfigurationTransitionIssue(code, message, path),),
    )


def transition_booking_configuration_to_production_choice(
    envelope,
    *,
    expected_booking_configuration_revision,
    expected_booking_configuration_fingerprint,
):
    """Atomically replace only the committed 5A policy with the 5C policy."""
    from .validation import validate_world

    try:
        configuration = envelope["simulation"]["configuration"]["booking"]
    except Exception:
        return _transition_rejection(
            None, "INVALID_WORLD_STATE", "world has no Booking configuration"
        )

    validation = validate_world(envelope)
    if not validation.is_valid:
        issue = validation.errors[0]
        return _transition_rejection(
            configuration, issue.code, issue.message, issue.path
        )
    if envelope["metadata"]["save_schema_version"] != 3:
        return _transition_rejection(
            configuration,
            "INVALID_WORLD_STATE",
            "Booking configuration transition requires schema 3",
            "$.metadata.save_schema_version",
        )
    revision = configuration["revision"]
    fingerprint = configuration["configuration_fingerprint"]
    if (
        type(expected_booking_configuration_revision) is not int
        or type(expected_booking_configuration_fingerprint) is not str
        or expected_booking_configuration_revision != revision
        or expected_booking_configuration_fingerprint != fingerprint
    ):
        return _transition_rejection(
            configuration,
            "STALE_BOOKING_CONFIGURATION",
            "expected Booking configuration revision or fingerprint does not match",
            status="STALE_REVISION",
        )

    if (
        revision >= 2
        and configuration["choice_policy"] == DEFAULT_BOOKING_CHOICE_POLICY
    ):
        return BookingConfigurationTransitionResult(
            "COMPLETED", revision, fingerprint, revision, fingerprint
        )
    if revision != 1 or configuration["choice_policy"] != LEGACY_BOOKING_CHOICE_POLICY:
        return _transition_rejection(
            configuration,
            "UNSUPPORTED_BOOKING_CONFIGURATION_TRANSITION",
            "only the exact committed revision-1 choice policy can transition",
            "$.simulation.configuration.booking.choice_policy",
        )

    candidate = deepcopy(envelope)
    updated = candidate["simulation"]["configuration"]["booking"]
    updated["revision"] = 2
    updated["choice_policy"] = deepcopy(DEFAULT_BOOKING_CHOICE_POLICY)
    updated["configuration_fingerprint"] = (
        calculate_booking_configuration_fingerprint(updated)
    )
    candidate_validation = validate_world(candidate)
    if not candidate_validation.is_valid:
        issue = candidate_validation.errors[0]
        return _transition_rejection(
            configuration, issue.code, issue.message, issue.path
        )
    envelope.clear()
    envelope.update(candidate)
    return BookingConfigurationTransitionResult(
        "COMPLETED",
        revision,
        fingerprint,
        updated["revision"],
        updated["configuration_fingerprint"],
        True,
    )


__all__ = (
    "BookingConfigurationTransitionIssue",
    "BookingConfigurationTransitionResult",
    "calculate_booking_configuration_fingerprint",
    "new_booking_configuration",
    "transition_booking_configuration_to_production_choice",
)
