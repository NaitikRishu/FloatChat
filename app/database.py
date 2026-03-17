from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS floats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wmo TEXT NOT NULL UNIQUE,
            region TEXT NOT NULL,
            platform_type TEXT NOT NULL,
            institution TEXT NOT NULL,
            is_bgc INTEGER NOT NULL DEFAULT 0,
            launch_date TEXT NOT NULL,
            last_reported_at TEXT NOT NULL,
            last_latitude REAL NOT NULL,
            last_longitude REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_code TEXT NOT NULL UNIQUE,
            float_id INTEGER NOT NULL REFERENCES floats(id) ON DELETE CASCADE,
            cycle_number INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            region TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            season TEXT NOT NULL,
            profile_type TEXT NOT NULL,
            max_depth_m REAL NOT NULL,
            surface_temperature_c REAL NOT NULL,
            surface_salinity_psu REAL NOT NULL,
            surface_oxygen_umol REAL,
            surface_chlorophyll_mg_m3 REAL,
            temperature_min_c REAL NOT NULL,
            temperature_max_c REAL NOT NULL,
            salinity_min_psu REAL NOT NULL,
            salinity_max_psu REAL NOT NULL,
            data_source TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            depth_m REAL NOT NULL,
            temperature_c REAL,
            salinity_psu REAL,
            oxygen_umol REAL,
            chlorophyll_mg_m3 REAL,
            nitrate_umol REAL,
            backscatter REAL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            kind TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            vector_json TEXT NOT NULL
        );
        """
    )
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(title, content, kind, content='documents', content_rowid='id');
            """
        )
    except sqlite3.OperationalError:
        pass
    connection.commit()


def clear_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DELETE FROM measurements;
        DELETE FROM profiles;
        DELETE FROM floats;
        DELETE FROM documents;
        """
    )
    try:
        connection.execute("DELETE FROM documents_fts")
    except sqlite3.OperationalError:
        pass
    connection.commit()


def insert_float(connection: sqlite3.Connection, payload: dict[str, object]) -> int:
    cursor = connection.execute(
        """
        INSERT INTO floats (
            wmo, region, platform_type, institution, is_bgc, launch_date,
            last_reported_at, last_latitude, last_longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["wmo"],
            payload["region"],
            payload["platform_type"],
            payload["institution"],
            int(payload["is_bgc"]),
            payload["launch_date"],
            payload["last_reported_at"],
            payload["last_latitude"],
            payload["last_longitude"],
        ),
    )
    return int(cursor.lastrowid)


def insert_profile(connection: sqlite3.Connection, payload: dict[str, object]) -> int:
    cursor = connection.execute(
        """
        INSERT INTO profiles (
            profile_code, float_id, cycle_number, observed_at, latitude, longitude,
            region, month, year, season, profile_type, max_depth_m,
            surface_temperature_c, surface_salinity_psu, surface_oxygen_umol,
            surface_chlorophyll_mg_m3, temperature_min_c, temperature_max_c,
            salinity_min_psu, salinity_max_psu, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["profile_code"],
            payload["float_id"],
            payload["cycle_number"],
            payload["observed_at"],
            payload["latitude"],
            payload["longitude"],
            payload["region"],
            payload["month"],
            payload["year"],
            payload["season"],
            payload["profile_type"],
            payload["max_depth_m"],
            payload["surface_temperature_c"],
            payload["surface_salinity_psu"],
            payload["surface_oxygen_umol"],
            payload["surface_chlorophyll_mg_m3"],
            payload["temperature_min_c"],
            payload["temperature_max_c"],
            payload["salinity_min_psu"],
            payload["salinity_max_psu"],
            payload["data_source"],
        ),
    )
    return int(cursor.lastrowid)


def insert_measurements(
    connection: sqlite3.Connection, profile_id: int, measurements: Iterable[dict[str, object]]
) -> None:
    connection.executemany(
        """
        INSERT INTO measurements (
            profile_id, depth_m, temperature_c, salinity_psu, oxygen_umol,
            chlorophyll_mg_m3, nitrate_umol, backscatter
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                profile_id,
                row["depth_m"],
                row.get("temperature_c"),
                row.get("salinity_psu"),
                row.get("oxygen_umol"),
                row.get("chlorophyll_mg_m3"),
                row.get("nitrate_umol"),
                row.get("backscatter"),
            )
            for row in measurements
        ],
    )


def insert_document(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    cursor = connection.execute(
        """
        INSERT OR REPLACE INTO documents (
            doc_id, title, content, kind, metadata_json, vector_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload["doc_id"],
            payload["title"],
            payload["content"],
            payload["kind"],
            json.dumps(payload["metadata"], sort_keys=True),
            json.dumps(payload["vector"]),
        ),
    )
    doc_rowid = cursor.lastrowid
    try:
        connection.execute(
            "INSERT OR REPLACE INTO documents_fts(rowid, title, content, kind) VALUES (?, ?, ?, ?)",
            (
                doc_rowid,
                payload["title"],
                payload["content"],
                payload["kind"],
            ),
        )
    except sqlite3.OperationalError:
        pass


def table_count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()
    return int(row["total"])
