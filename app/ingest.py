from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .database import (
    clear_database,
    connect,
    initialize_schema,
    insert_document,
    insert_float,
    insert_measurements,
    insert_profile,
    table_count,
)
from .demo_data import generate_demo_dataset
from .query_engine import embed_text


def bootstrap_database(db_path: Path, reset: bool = False) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    if reset or table_count(connection, "floats") == 0:
        seed_demo_data(connection)
    connection.close()


def seed_demo_data(connection: sqlite3.Connection) -> None:
    clear_database(connection)
    dataset = generate_demo_dataset()
    float_lookup: dict[str, int] = {}
    profile_lookup: dict[str, int] = {}

    for float_payload in dataset["floats"]:
        float_lookup[str(float_payload["wmo"])] = insert_float(connection, float_payload)

    for profile_payload in dataset["profiles"]:
        payload = dict(profile_payload)
        payload["float_id"] = float_lookup[str(payload["wmo"])]
        profile_lookup[str(payload["profile_code"])] = insert_profile(connection, payload)

    grouped_measurements: dict[str, list[dict[str, object]]] = {}
    for measurement in dataset["measurements"]:
        grouped_measurements.setdefault(str(measurement["profile_code"]), []).append(measurement)
    for profile_code, rows in grouped_measurements.items():
        insert_measurements(connection, profile_lookup[profile_code], rows)

    for document in dataset["documents"]:
        payload = dict(document)
        payload["vector"] = embed_text(payload["content"])
        insert_document(connection, payload)

    connection.commit()


def ingest_netcdf_files(db_path: Path, paths: list[Path]) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    for path in paths:
        ingest_single_netcdf(connection, path)
    connection.commit()
    connection.close()


def ingest_single_netcdf(connection: sqlite3.Connection, path: Path) -> None:
    try:
        import xarray as xr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "NetCDF ingestion needs xarray installed. The demo app still runs without it."
        ) from exc

    dataset = xr.open_dataset(path)
    if "PLATFORM_NUMBER" not in dataset:
        raise RuntimeError(f"{path} is missing PLATFORM_NUMBER and does not look like an Argo profile file.")

    platform_value = str(dataset["PLATFORM_NUMBER"].values[0]).strip()
    float_payload = {
        "wmo": platform_value,
        "region": "External NetCDF import",
        "platform_type": "Imported Argo float",
        "institution": "External source",
        "is_bgc": int("DOXY" in dataset or "CHLA" in dataset),
        "launch_date": "2023-01-01",
        "last_reported_at": "2023-01-01T00:00:00",
        "last_latitude": float(dataset["LATITUDE"].values[0]),
        "last_longitude": float(dataset["LONGITUDE"].values[0]),
    }
    try:
        float_id = insert_float(connection, float_payload)
    except sqlite3.IntegrityError:
        row = connection.execute("SELECT id FROM floats WHERE wmo = ?", (platform_value,)).fetchone()
        float_id = int(row["id"])

    levels = dataset["PRES"].values.tolist()
    profile_code = f"{platform_value}_{path.stem}"
    observed_at = "2023-01-01T00:00:00"
    profile_payload = {
        "profile_code": profile_code,
        "float_id": float_id,
        "cycle_number": 1,
        "observed_at": observed_at,
        "latitude": float(dataset["LATITUDE"].values[0]),
        "longitude": float(dataset["LONGITUDE"].values[0]),
        "region": "External NetCDF import",
        "month": 1,
        "year": 2023,
        "season": "Imported",
        "profile_type": "BGC" if float_payload["is_bgc"] else "Core",
        "max_depth_m": float(max(levels)),
        "surface_temperature_c": float(dataset["TEMP"].values[0]),
        "surface_salinity_psu": float(dataset["PSAL"].values[0]),
        "surface_oxygen_umol": float(dataset["DOXY"].values[0]) if "DOXY" in dataset else None,
        "surface_chlorophyll_mg_m3": float(dataset["CHLA"].values[0]) if "CHLA" in dataset else None,
        "temperature_min_c": float(min(dataset["TEMP"].values)),
        "temperature_max_c": float(max(dataset["TEMP"].values)),
        "salinity_min_psu": float(min(dataset["PSAL"].values)),
        "salinity_max_psu": float(max(dataset["PSAL"].values)),
        "data_source": str(path.name),
    }
    try:
        profile_id = insert_profile(connection, profile_payload)
    except sqlite3.IntegrityError:
        return

    measurement_rows = []
    for idx, depth in enumerate(levels):
        measurement_rows.append(
            {
                "depth_m": float(depth),
                "temperature_c": float(dataset["TEMP"].values[idx]),
                "salinity_psu": float(dataset["PSAL"].values[idx]),
                "oxygen_umol": float(dataset["DOXY"].values[idx]) if "DOXY" in dataset else None,
                "chlorophyll_mg_m3": float(dataset["CHLA"].values[idx]) if "CHLA" in dataset else None,
                "nitrate_umol": None,
                "backscatter": None,
            }
        )
    insert_measurements(connection, profile_id, measurement_rows)
    insert_document(
        connection,
        {
            "doc_id": f"import:{path.name}",
            "title": f"Imported NetCDF {path.name}",
            "content": (
                f"Imported platform {platform_value} from {path.name} with {len(measurement_rows)} depth levels "
                f"and {'BGC' if float_payload['is_bgc'] else 'core'} variables."
            ),
            "kind": "import",
            "metadata": {"source_path": str(path)},
            "vector": embed_text(path.name),
        },
    )


def export_catalog_snapshot(db_path: Path, output_path: Path) -> None:
    connection = connect(db_path)
    rows = connection.execute(
        """
        SELECT f.wmo, f.region, f.is_bgc, p.profile_code, p.observed_at, p.latitude, p.longitude
        FROM profiles p
        JOIN floats f ON f.id = p.float_id
        ORDER BY datetime(p.observed_at) DESC
        LIMIT 50
        """
    ).fetchall()
    payload = [
        {
            "wmo": row["wmo"],
            "region": row["region"],
            "is_bgc": bool(row["is_bgc"]),
            "profile_code": row["profile_code"],
            "observed_at": row["observed_at"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }
        for row in rows
    ]
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    connection.close()
