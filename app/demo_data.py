from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass


DEPTH_LEVELS = [0, 10, 25, 50, 75, 100, 150, 200, 300, 500, 700, 1000]


@dataclass(frozen=True)
class RegionSeed:
    name: str
    lat_range: tuple[float, float]
    lon_range: tuple[float, float]
    base_temp: float
    base_salinity: float
    description: str


REGIONS: list[RegionSeed] = [
    RegionSeed(
        name="Arabian Sea",
        lat_range=(8.0, 24.0),
        lon_range=(58.0, 72.0),
        base_temp=28.8,
        base_salinity=36.3,
        description="High-salinity northern Indian Ocean basin with strong monsoon-driven variability.",
    ),
    RegionSeed(
        name="Bay of Bengal",
        lat_range=(6.0, 22.0),
        lon_range=(81.0, 96.0),
        base_temp=29.1,
        base_salinity=34.1,
        description="Freshened surface waters and strong stratification influenced by river discharge and monsoon forcing.",
    ),
    RegionSeed(
        name="Equatorial Indian Ocean",
        lat_range=(-4.0, 4.0),
        lon_range=(66.0, 92.0),
        base_temp=29.4,
        base_salinity=35.0,
        description="Warm equatorial corridor with energetic zonal currents and strong seasonal signals.",
    ),
    RegionSeed(
        name="Southern Indian Ocean",
        lat_range=(-38.0, -16.0),
        lon_range=(70.0, 110.0),
        base_temp=19.5,
        base_salinity=35.1,
        description="Cooler subtropical to subantarctic waters with deeper mixed layers and strong seasonality.",
    ),
    RegionSeed(
        name="Western Indian Ocean",
        lat_range=(-18.0, 4.0),
        lon_range=(48.0, 65.0),
        base_temp=27.6,
        base_salinity=35.4,
        description="Western boundary current corridor shaped by eddies, Somali Current shifts, and tropical exchanges.",
    ),
]


def month_range(start: dt.date, end: dt.date) -> list[dt.date]:
    current = dt.date(start.year, start.month, 1)
    dates: list[dt.date] = []
    while current <= end:
        dates.append(current)
        if current.month == 12:
            current = dt.date(current.year + 1, 1, 1)
        else:
            current = dt.date(current.year, current.month + 1, 1)
    return dates


def season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "Northeast Monsoon"
    if month in (3, 4, 5):
        return "Pre-Monsoon"
    if month in (6, 7, 8, 9):
        return "Southwest Monsoon"
    return "Inter-Monsoon"


def bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def generate_demo_dataset() -> dict[str, list[dict[str, object]]]:
    rng = random.Random(17)
    floats: list[dict[str, object]] = []
    profiles: list[dict[str, object]] = []
    measurements: list[dict[str, object]] = []
    documents: list[dict[str, object]] = []

    schedule = month_range(dt.date(2023, 1, 1), dt.date(2026, 3, 1))

    for region_index, region in enumerate(REGIONS):
        for local_idx in range(4):
            float_number = region_index * 4 + local_idx + 1
            wmo = f"490{float_number:04d}"
            is_bgc = (float_number + region_index) % 2 == 0
            center_lat = sum(region.lat_range) / 2
            center_lon = sum(region.lon_range) / 2
            launch_date = dt.date(2022, 6, 1) + dt.timedelta(days=float_number * 8)
            float_payload = {
                "wmo": wmo,
                "region": region.name,
                "platform_type": "APEX profiling float" if is_bgc else "Core Argo float",
                "institution": "Indian Ocean OceanLab",
                "is_bgc": is_bgc,
                "launch_date": launch_date.isoformat(),
                "last_reported_at": "",
                "last_latitude": center_lat,
                "last_longitude": center_lon,
            }

            all_profile_rows: list[dict[str, object]] = []
            for cycle_number, date_value in enumerate(schedule, start=1):
                month_angle = ((date_value.month - 1) / 12.0) * math.tau
                drift_angle = (cycle_number / 7.0) + region_index
                latitude = bounded(
                    center_lat
                    + math.sin(drift_angle) * (region.lat_range[1] - region.lat_range[0]) * 0.16
                    + rng.uniform(-0.75, 0.75),
                    region.lat_range[0],
                    region.lat_range[1],
                )
                longitude = bounded(
                    center_lon
                    + math.cos(drift_angle * 0.85) * (region.lon_range[1] - region.lon_range[0]) * 0.18
                    + rng.uniform(-0.95, 0.95),
                    region.lon_range[0],
                    region.lon_range[1],
                )
                seasonal_boost = math.sin(month_angle - 0.7) * (2.0 if latitude >= 0 else 1.3)
                latitude_penalty = abs(latitude) * 0.11
                surface_temp = region.base_temp + seasonal_boost - latitude_penalty + rng.uniform(-0.5, 0.5)
                surface_salinity = region.base_salinity + (abs(latitude) / 24.0) * 0.35 + rng.uniform(-0.18, 0.18)
                if region.name == "Bay of Bengal":
                    surface_salinity -= 0.5 + 0.25 * math.sin(month_angle)
                if region.name == "Arabian Sea":
                    surface_salinity += 0.25 + 0.18 * math.cos(month_angle)

                surface_oxygen = 208.0 - (surface_temp - 18.0) * 2.2 + rng.uniform(-7.0, 7.0)
                surface_chl = max(0.04, 0.19 + rng.uniform(-0.03, 0.08))
                profile_code = f"{wmo}_{date_value:%Y%m}"
                observed_at = (
                    dt.datetime.combine(date_value, dt.time(6, 0))
                    + dt.timedelta(hours=(local_idx * 5) + region_index)
                ).isoformat()
                profile_payload = {
                    "wmo": wmo,
                    "profile_code": profile_code,
                    "cycle_number": cycle_number,
                    "observed_at": observed_at,
                    "latitude": round(latitude, 3),
                    "longitude": round(longitude, 3),
                    "region": region.name,
                    "month": date_value.month,
                    "year": date_value.year,
                    "season": season_for_month(date_value.month),
                    "profile_type": "BGC" if is_bgc else "Core",
                    "max_depth_m": 1000.0,
                    "surface_temperature_c": round(surface_temp, 3),
                    "surface_salinity_psu": round(surface_salinity, 3),
                    "surface_oxygen_umol": round(surface_oxygen, 3) if is_bgc else None,
                    "surface_chlorophyll_mg_m3": round(surface_chl, 4) if is_bgc else None,
                    "temperature_min_c": 2.0,
                    "temperature_max_c": round(surface_temp, 3),
                    "salinity_min_psu": round(surface_salinity - 0.5, 3),
                    "salinity_max_psu": round(surface_salinity + 0.6, 3),
                    "data_source": "deterministic-demo",
                }
                level_rows: list[dict[str, object]] = []
                for depth in DEPTH_LEVELS:
                    deep_fraction = depth / DEPTH_LEVELS[-1]
                    temperature = max(
                        1.7,
                        surface_temp
                        - 15.2 * (1 - math.exp(-depth / 240.0))
                        - 1.6 * deep_fraction
                        + rng.uniform(-0.24, 0.24),
                    )
                    salinity = (
                        surface_salinity
                        + 0.72 * (1 - math.exp(-depth / 280.0))
                        - 0.16 * deep_fraction
                        + rng.uniform(-0.03, 0.03)
                    )
                    oxygen = (
                        surface_oxygen
                        - 92.0 * (1 - math.exp(-depth / 240.0))
                        + 18.0 * deep_fraction
                        + rng.uniform(-4.0, 4.0)
                        if is_bgc
                        else None
                    )
                    chlorophyll = (
                        max(0.01, surface_chl * math.exp(-depth / 85.0) + rng.uniform(-0.01, 0.015))
                        if is_bgc
                        else None
                    )
                    nitrate = (
                        max(0.05, 0.8 + 15.0 * deep_fraction + rng.uniform(-0.3, 0.3))
                        if is_bgc
                        else None
                    )
                    backscatter = (
                        max(0.0001, 0.0015 + depth * 0.000004 + rng.uniform(-0.00015, 0.00015))
                        if is_bgc
                        else None
                    )
                    level_rows.append(
                        {
                            "profile_code": profile_code,
                            "depth_m": depth,
                            "temperature_c": round(temperature, 3),
                            "salinity_psu": round(salinity, 3),
                            "oxygen_umol": round(oxygen, 3) if oxygen is not None else None,
                            "chlorophyll_mg_m3": round(chlorophyll, 4) if chlorophyll is not None else None,
                            "nitrate_umol": round(nitrate, 3) if nitrate is not None else None,
                            "backscatter": round(backscatter, 5) if backscatter is not None else None,
                        }
                    )

                all_profile_rows.append(profile_payload)
                measurements.extend(level_rows)

            last_profile = all_profile_rows[-1]
            float_payload["last_reported_at"] = last_profile["observed_at"]
            float_payload["last_latitude"] = last_profile["latitude"]
            float_payload["last_longitude"] = last_profile["longitude"]
            floats.append(float_payload)
            profiles.extend(all_profile_rows)

            documents.append(
                {
                    "doc_id": f"float:{wmo}",
                    "title": f"ARGO float {wmo}",
                    "content": (
                        f"Float {wmo} operates in the {region.name}. "
                        f"It is a {'BGC-enabled' if is_bgc else 'core'} platform from "
                        f"{float_payload['institution']} with repeated profiles through 1000 m. "
                        f"Latest position is {float_payload['last_latitude']}N, {float_payload['last_longitude']}E."
                    ),
                    "kind": "float",
                    "metadata": {
                        "wmo": wmo,
                        "region": region.name,
                        "is_bgc": is_bgc,
                    },
                }
            )

    for region in REGIONS:
        documents.append(
            {
                "doc_id": f"region:{region.name.lower().replace(' ', '-')}",
                "title": region.name,
                "content": region.description,
                "kind": "region",
                "metadata": {"region": region.name},
            }
        )

    return {
        "floats": floats,
        "profiles": profiles,
        "measurements": measurements,
        "documents": documents,
    }
