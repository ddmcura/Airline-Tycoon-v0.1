"""Validation of the optional authoritative Model 4 suitability inputs."""

AIR_SUITABILITY_CONTRACT = "MODEL4_AIR_SUITABILITY_V1"


def validate_air_suitability_configuration(value):
    fields = {
        "contract", "configuration_version", "interpolation_policy",
        "right_boundary_policy", "same_ground_network_points",
        "separated_ground_network_points",
    }
    if type(value) is not dict or set(value) != fields:
        raise ValueError("air_suitability_configuration must contain exactly the canonical fields")
    for field, expected in (
        ("contract", AIR_SUITABILITY_CONTRACT),
        ("interpolation_policy", "PIECEWISE_LINEAR_RATIONAL_V1"),
        ("right_boundary_policy", "HOLD_LAST"),
    ):
        if value[field] != expected:
            raise ValueError(f"unsupported air_suitability_configuration.{field}")
    version = value["configuration_version"]
    if not isinstance(version, str) or not version.strip() or version != version.strip():
        raise ValueError("air_suitability_configuration.configuration_version must be non-empty canonical text")
    for field in ("same_ground_network_points", "separated_ground_network_points"):
        points = value[field]
        if type(points) is not list or len(points) < 2:
            raise ValueError(f"{field} requires at least two points")
        previous = -1
        for index, point in enumerate(points):
            if type(point) is not dict or set(point) != {"distance_m", "suitability_bps"}:
                raise ValueError(f"{field}[{index}] must contain distance_m and suitability_bps")
            distance, suitability = point["distance_m"], point["suitability_bps"]
            if type(distance) is not int or distance <= previous or (index == 0 and distance != 0):
                raise ValueError(f"{field}[{index}].distance_m must strictly increase from zero")
            if type(suitability) is not int or not 0 <= suitability <= 10000:
                raise ValueError(f"{field}[{index}].suitability_bps must be an integer 0..10000")
            previous = distance


def validate_air_suitability_airport(record, *, required=False):
    if required or "ground_network_id" in record:
        network = record.get("ground_network_id")
        if not isinstance(network, str) or not network.strip() or network != network.strip():
            raise ValueError("ground_network_id must be non-empty canonical text")
    if required or "tourism_pull_ppm" in record:
        tourism = record.get("tourism_pull_ppm")
        if type(tourism) is not int or not 0 <= tourism <= 5000000:
            raise ValueError("tourism_pull_ppm must be an integer 0..5000000")
