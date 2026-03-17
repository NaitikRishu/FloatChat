from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Any


MONTH_LOOKUP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

REGION_KEYWORDS = {
    "arabian sea": "Arabian Sea",
    "bay of bengal": "Bay of Bengal",
    "equatorial indian ocean": "Equatorial Indian Ocean",
    "equator": "Equatorial Indian Ocean",
    "southern indian ocean": "Southern Indian Ocean",
    "western indian ocean": "Western Indian Ocean",
    "indian ocean": None,
}

PARAMETER_COLUMNS = {
    "temperature": ("temperature_c", "temperature", "deg C"),
    "salinity": ("salinity_psu", "salinity", "PSU"),
    "oxygen": ("oxygen_umol", "oxygen", "umol/kg"),
    "chlorophyll": ("chlorophyll_mg_m3", "chlorophyll", "mg/m^3"),
    "nitrate": ("nitrate_umol", "nitrate", "umol/L"),
    "backscatter": ("backscatter", "backscatter", "sr^-1"),
}

EXPLANATION_COPY = {
    "salinity": (
        "Salinity describes how much dissolved salt is present in seawater. "
        "Oceanographers use it to understand water mass structure, density, stratification, "
        "and circulation because saltier water is generally denser than fresher water."
    ),
    "temperature": (
        "Temperature measures how warm or cold the seawater is at each depth. "
        "It helps reveal surface heating, thermocline structure, mixing, and large-scale ocean circulation."
    ),
    "oxygen": (
        "Dissolved oxygen shows how much oxygen is available in seawater. "
        "It is useful for understanding ventilation, biological activity, and low-oxygen zones."
    ),
    "chlorophyll": (
        "Chlorophyll is a proxy for phytoplankton biomass in the upper ocean. "
        "It helps indicate where biological productivity is stronger or weaker."
    ),
    "nitrate": (
        "Nitrate is a key nutrient used by marine plants and phytoplankton. "
        "Its distribution helps explain biological productivity and nutrient limitation."
    ),
    "backscatter": (
        "Optical backscatter measures how much light is scattered by particles in seawater. "
        "It is often used as an indicator of suspended material and particle-rich layers."
    ),
    "argo": (
        "Argo is a global ocean observing program built around autonomous profiling floats. "
        "These floats drift through the ocean, periodically dive and rise, and transmit vertical profiles such as temperature and salinity."
    ),
    "bgc": (
        "BGC stands for biogeochemical. In Argo, BGC floats measure extra variables like oxygen, chlorophyll, nitrate, or optical signals in addition to core temperature and salinity."
    ),
    "ctd": (
        "CTD stands for Conductivity, Temperature, and Depth. It is a common oceanographic instrument package used to characterize seawater properties through the water column."
    ),
    "profile": (
        "A profile is a vertical slice of the ocean collected from the surface down through depth. "
        "It shows how variables like temperature or salinity change from shallow water to deeper layers."
    ),
}

SMALL_TALK_RESPONSES = {
    "hi": "Hi. Ask me about ARGO floats, salinity, BGC trends, trajectories, or nearest floats in the Indian Ocean.",
    "hello": "Hello. I can explain ocean terms or help you explore ARGO float data with maps, profiles, and comparisons.",
    "hey": "Hey. Try asking for a concept explanation or a data query like salinity profiles near the equator.",
    "thanks": "Happy to help. You can ask a follow-up about ocean concepts or request a specific ARGO data view.",
    "thank you": "Happy to help. You can ask a follow-up about ocean concepts or request a specific ARGO data view.",
}


@dataclass
class QueryPlan:
    intent: str
    question: str
    parameter: str
    concept: str | None
    region: str | None
    lat_range: tuple[float, float] | None
    lon_range: tuple[float, float] | None
    start_date: str | None
    end_date: str | None
    nearest_point: tuple[float, float] | None


def parse_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % dimensions
        vector[bucket] += 1.0
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / length, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def search_documents(connection: sqlite3.Connection, query: str, limit: int = 4) -> list[dict[str, Any]]:
    query_vector = embed_text(query)
    rows = connection.execute(
        "SELECT doc_id, title, content, kind, metadata_json, vector_json FROM documents"
    ).fetchall()
    scored = []
    for row in rows:
        score = cosine_similarity(query_vector, json.loads(row["vector_json"]))
        metadata = json.loads(row["metadata_json"])
        scored.append(
            {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "content": row["content"],
                "kind": row["kind"],
                "metadata": metadata,
                "score": round(score, 4),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def normalize_region(question: str) -> str | None:
    lowered = question.lower()
    for key, value in REGION_KEYWORDS.items():
        if key in lowered:
            return value
    return None


def infer_parameter(question: str) -> str:
    lowered = question.lower()
    for parameter in PARAMETER_COLUMNS:
        if parameter in lowered:
            return parameter
    if "bgc" in lowered:
        return "oxygen"
    return "temperature"


def infer_concept(question: str) -> str | None:
    lowered = question.lower()
    for concept in EXPLANATION_COPY:
        if concept in lowered:
            return concept
    return None


def is_explanation_question(question: str) -> bool:
    lowered = question.lower().strip()
    explanation_starts = (
        "what is ",
        "what are ",
        "define ",
        "explain ",
        "meaning of ",
        "tell me about ",
    )
    has_explicit_data_scope = any(
        phrase in lowered
        for phrase in ("show me", "compare", "nearest", "closest", "profile", "profiles", "plot", "map")
    )
    return lowered.startswith(explanation_starts) and not has_explicit_data_scope


def infer_small_talk(question: str) -> str | None:
    lowered = question.lower().strip()
    compact = re.sub(r"[!?.,]+$", "", lowered)
    return compact if compact in SMALL_TALK_RESPONSES else None


def infer_time_window(question: str, connection: sqlite3.Connection) -> tuple[str | None, str | None]:
    lowered = question.lower()
    month_match = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
        lowered,
    )
    if month_match:
        month = MONTH_LOOKUP[month_match.group(1)]
        year = int(month_match.group(2))
        start = dt.date(year, month, 1)
        if month == 12:
            end = dt.date(year + 1, 1, 1)
        else:
            end = dt.date(year, month + 1, 1)
        return start.isoformat(), end.isoformat()

    last_months_match = re.search(r"last\s+(\d+)\s+months?", lowered)
    if last_months_match:
        count = int(last_months_match.group(1))
        latest = connection.execute("SELECT MAX(date(observed_at)) AS latest FROM profiles").fetchone()
        latest_date = dt.date.fromisoformat(latest["latest"])
        start_month = latest_date.month - count + 1
        start_year = latest_date.year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start = dt.date(start_year, start_month, 1)
        if latest_date.month == 12:
            end = dt.date(latest_date.year + 1, 1, 1)
        else:
            end = dt.date(latest_date.year, latest_date.month + 1, 1)
        return start.isoformat(), end.isoformat()
    return None, None


def infer_coordinates(question: str) -> tuple[float, float] | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", question)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def build_plan(
    connection: sqlite3.Connection,
    question: str,
    selected_point: tuple[float, float] | None = None,
) -> QueryPlan:
    lowered = question.lower()
    region = normalize_region(question)
    parameter = infer_parameter(question)
    start_date, end_date = infer_time_window(question, connection)
    nearest_point = infer_coordinates(question) or selected_point
    concept = infer_concept(question)
    small_talk_key = infer_small_talk(question)

    lat_range = None
    lon_range = None
    if "equator" in lowered:
        lat_range = (-5.0, 5.0)
    if "near" in lowered and nearest_point:
        lat, lon = nearest_point
        lat_range = (lat - 4.0, lat + 4.0)
        lon_range = (lon - 5.0, lon + 5.0)

    if small_talk_key:
        intent = "small_talk"
    elif is_explanation_question(question) and concept:
        intent = "explanation"
    elif "nearest" in lowered or "closest" in lowered:
        intent = "nearest_floats"
    elif "compare" in lowered and ("bgc" in lowered or parameter in {"oxygen", "chlorophyll", "nitrate", "backscatter"}):
        intent = "compare_bgc"
    elif "trajectory" in lowered or "track" in lowered:
        intent = "trajectory"
    elif "profile" in lowered or "profiles" in lowered or parameter in {"salinity", "temperature"}:
        intent = "profiles"
    else:
        intent = "summary"

    return QueryPlan(
        intent=intent,
        question=question,
        parameter=parameter,
        concept=small_talk_key or concept,
        region=region,
        lat_range=lat_range,
        lon_range=lon_range,
        start_date=start_date,
        end_date=end_date,
        nearest_point=nearest_point,
    )


def plan_from_payload(
    connection: sqlite3.Connection,
    question: str,
    payload: dict[str, Any],
    selected_point: tuple[float, float] | None = None,
) -> QueryPlan:
    fallback = build_plan(connection, question, selected_point=selected_point)
    intent = payload.get("intent")
    if intent not in {"profiles", "compare_bgc", "nearest_floats", "trajectory", "summary"}:
        intent = fallback.intent

    parameter = payload.get("parameter")
    if parameter not in PARAMETER_COLUMNS:
        parameter = fallback.parameter

    region = payload.get("region") or fallback.region
    start_date = parse_iso_date(payload.get("start_date")) or fallback.start_date
    end_date = parse_iso_date(payload.get("end_date")) or fallback.end_date

    lat_range = fallback.lat_range
    if payload.get("use_lat_range"):
        lat_min = float(payload.get("lat_min", -5.0))
        lat_max = float(payload.get("lat_max", 5.0))
        lat_range = (min(lat_min, lat_max), max(lat_min, lat_max))

    lon_range = fallback.lon_range
    if payload.get("use_lon_range"):
        lon_min = float(payload.get("lon_min", 40.0))
        lon_max = float(payload.get("lon_max", 110.0))
        lon_range = (min(lon_min, lon_max), max(lon_min, lon_max))

    nearest_point = fallback.nearest_point
    if payload.get("use_point"):
        nearest_point = (
            float(payload.get("point_lat", selected_point[0] if selected_point else 0.0)),
            float(payload.get("point_lon", selected_point[1] if selected_point else 80.0)),
        )

    return QueryPlan(
        intent=intent,
        question=question,
        parameter=parameter,
        concept=infer_small_talk(question) or infer_concept(question),
        region=region,
        lat_range=lat_range,
        lon_range=lon_range,
        start_date=start_date,
        end_date=end_date,
        nearest_point=nearest_point,
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def compile_profile_filters(plan: QueryPlan) -> tuple[str, list[Any]]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if plan.region:
        clauses.append("p.region = ?")
        params.append(plan.region)
    if plan.start_date:
        clauses.append("date(p.observed_at) >= date(?)")
        params.append(plan.start_date)
    if plan.end_date:
        clauses.append("date(p.observed_at) < date(?)")
        params.append(plan.end_date)
    if plan.lat_range:
        clauses.append("p.latitude BETWEEN ? AND ?")
        params.extend(plan.lat_range)
    if plan.lon_range:
        clauses.append("p.longitude BETWEEN ? AND ?")
        params.extend(plan.lon_range)
    return " AND ".join(clauses), params


def execute_profiles(connection: sqlite3.Connection, plan: QueryPlan) -> dict[str, Any]:
    column, label, unit = PARAMETER_COLUMNS[plan.parameter]
    where_sql, params = compile_profile_filters(plan)
    sql = f"""
        SELECT p.id, p.profile_code, p.observed_at, p.latitude, p.longitude, p.region,
               f.wmo, f.is_bgc, p.surface_temperature_c, p.surface_salinity_psu
        FROM profiles p
        JOIN floats f ON f.id = p.float_id
        WHERE {where_sql}
        ORDER BY datetime(p.observed_at) DESC
        LIMIT 5
    """
    profile_rows = connection.execute(sql, params).fetchall()
    payload_profiles = []
    for row in profile_rows:
        series = connection.execute(
            f"""
            SELECT depth_m, {column} AS value
            FROM measurements
            WHERE profile_id = ? AND {column} IS NOT NULL
            ORDER BY depth_m ASC
            """,
            (row["id"],),
        ).fetchall()
        payload_profiles.append(
            {
                "profile_code": row["profile_code"],
                "wmo": row["wmo"],
                "observed_at": row["observed_at"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "region": row["region"],
                "series": [{"depth_m": item["depth_m"], "value": item["value"]} for item in series],
            }
        )
    summary = (
        f"Retrieved {len(payload_profiles)} {label} profiles"
        + (f" in {plan.region}" if plan.region else "")
        + (f" between {plan.start_date} and {plan.end_date}" if plan.start_date else "")
        + "."
    )
    return {
        "kind": "profiles",
        "title": f"{label.title()} profiles",
        "unit": unit,
        "sql": " ".join(sql.split()),
        "summary": summary,
        "profiles": payload_profiles,
    }


def execute_bgc_compare(connection: sqlite3.Connection, plan: QueryPlan) -> dict[str, Any]:
    where_sql, params = compile_profile_filters(plan)
    sql = f"""
        SELECT substr(p.observed_at, 1, 7) AS month,
               AVG(p.surface_oxygen_umol) AS oxygen,
               AVG(p.surface_chlorophyll_mg_m3) AS chlorophyll,
               AVG(m.nitrate_umol) AS nitrate,
               AVG(m.backscatter) AS backscatter
        FROM profiles p
        LEFT JOIN measurements m ON m.profile_id = p.id AND m.depth_m = 150
        WHERE {where_sql}
          AND p.profile_type = 'BGC'
        GROUP BY substr(p.observed_at, 1, 7)
        ORDER BY month ASC
    """
    rows = connection.execute(sql, params).fetchall()
    series = [
        {
            "month": row["month"],
            "oxygen": round(row["oxygen"], 3) if row["oxygen"] is not None else None,
            "chlorophyll": round(row["chlorophyll"], 4) if row["chlorophyll"] is not None else None,
            "nitrate": round(row["nitrate"], 3) if row["nitrate"] is not None else None,
            "backscatter": round(row["backscatter"], 5) if row["backscatter"] is not None else None,
        }
        for row in rows
    ]
    summary = (
        f"Compared BGC indicators across {len(series)} monthly bins"
        + (f" for {plan.region}" if plan.region else "")
        + "."
    )
    return {
        "kind": "bgc_compare",
        "title": "BGC comparison",
        "sql": " ".join(sql.split()),
        "summary": summary,
        "series": series,
    }


def execute_nearest(connection: sqlite3.Connection, plan: QueryPlan) -> dict[str, Any]:
    point = plan.nearest_point or (0.0, 80.0)
    sql = """
        SELECT wmo, region, is_bgc, last_latitude, last_longitude, last_reported_at
        FROM floats
    """
    rows = connection.execute(sql).fetchall()
    candidates = []
    for row in rows:
        distance = haversine_km(point[0], point[1], row["last_latitude"], row["last_longitude"])
        candidates.append(
            {
                "wmo": row["wmo"],
                "region": row["region"],
                "is_bgc": bool(row["is_bgc"]),
                "latitude": row["last_latitude"],
                "longitude": row["last_longitude"],
                "last_reported_at": row["last_reported_at"],
                "distance_km": round(distance, 1),
            }
        )
    candidates.sort(key=lambda item: item["distance_km"])
    summary = (
        f"Found {min(5, len(candidates))} nearest floats to {point[0]:.2f}, {point[1]:.2f}."
    )
    return {
        "kind": "nearest_floats",
        "title": "Nearest ARGO floats",
        "sql": " ".join(sql.split()),
        "summary": summary,
        "point": {"lat": point[0], "lon": point[1]},
        "rows": candidates[:5],
    }


def execute_trajectory(connection: sqlite3.Connection, plan: QueryPlan) -> dict[str, Any]:
    where_sql, params = compile_profile_filters(plan)
    sql = f"""
        SELECT f.wmo, p.observed_at, p.latitude, p.longitude, p.region
        FROM profiles p
        JOIN floats f ON f.id = p.float_id
        WHERE {where_sql}
        ORDER BY f.wmo ASC, datetime(p.observed_at) ASC
        LIMIT 120
    """
    rows = connection.execute(sql, params).fetchall()
    tracks: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        tracks.setdefault(row["wmo"], []).append(
            {
                "observed_at": row["observed_at"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "region": row["region"],
            }
        )
    return {
        "kind": "trajectory",
        "title": "ARGO trajectories",
        "sql": " ".join(sql.split()),
        "summary": f"Loaded {len(tracks)} float tracks for quick trajectory comparison.",
        "tracks": tracks,
    }


def execute_summary(connection: sqlite3.Connection, plan: QueryPlan) -> dict[str, Any]:
    where_sql, params = compile_profile_filters(plan)
    sql = f"""
        SELECT COUNT(*) AS profiles,
               COUNT(DISTINCT p.float_id) AS floats,
               AVG(p.surface_temperature_c) AS avg_temp,
               AVG(p.surface_salinity_psu) AS avg_salinity
        FROM profiles p
        WHERE {where_sql}
    """
    row = connection.execute(sql, params).fetchone()
    return {
        "kind": "summary",
        "title": "Query summary",
        "sql": " ".join(sql.split()),
        "summary": (
            f"Matched {row['profiles']} profiles from {row['floats']} floats. "
            f"Average surface temperature is {row['avg_temp']:.2f} C and "
            f"average surface salinity is {row['avg_salinity']:.2f} PSU."
        ),
        "stats": {
            "profiles": row["profiles"],
            "floats": row["floats"],
            "avg_temp": round(row["avg_temp"], 3) if row["avg_temp"] is not None else None,
            "avg_salinity": round(row["avg_salinity"], 3) if row["avg_salinity"] is not None else None,
        },
    }


def execute_explanation(plan: QueryPlan) -> dict[str, Any]:
    concept = plan.concept or plan.parameter
    explanation = EXPLANATION_COPY.get(
        concept,
        "This concept is part of ocean observation and interpretation, but I do not have a richer glossary entry for it yet.",
    )
    return {
        "kind": "explanation",
        "title": f"What is {concept}?",
        "sql": "No SQL required for a concept explanation.",
        "summary": explanation,
        "concept": concept,
        "details": explanation,
    }


def execute_small_talk(plan: QueryPlan) -> dict[str, Any]:
    key = (plan.concept or "").lower()
    message = SMALL_TALK_RESPONSES.get(
        key,
        "Ask me about ARGO floats, ocean variables, or specific Indian Ocean profile queries.",
    )
    return {
        "kind": "small_talk",
        "title": "Conversation",
        "sql": "No SQL required for a conversational response.",
        "summary": message,
        "details": message,
    }


def run_query(
    connection: sqlite3.Connection,
    question: str,
    selected_point: tuple[float, float] | None = None,
    openai_service: Any | None = None,
) -> dict[str, Any]:
    retrieval = search_documents(connection, question)
    provider_name = getattr(openai_service, "provider", "llm")
    plan_source = "local"
    answer_source = "local"
    plan = build_plan(connection, question, selected_point=selected_point)

    latest_row = connection.execute("SELECT MAX(date(observed_at)) AS latest FROM profiles").fetchone()
    latest_catalog_date = latest_row["latest"] if latest_row else None
    if openai_service and getattr(openai_service, "enabled", False):
        try:
            ai_plan = openai_service.plan_query(
                question=question,
                selected_point=selected_point,
                retrieval=retrieval,
                latest_catalog_date=latest_catalog_date,
            )
        except Exception:
            ai_plan = None
        if ai_plan:
            plan = plan_from_payload(connection, question, ai_plan, selected_point=selected_point)
            plan_source = provider_name

    if plan.intent == "nearest_floats":
        result = execute_nearest(connection, plan)
    elif plan.intent == "small_talk":
        result = execute_small_talk(plan)
    elif plan.intent == "explanation":
        result = execute_explanation(plan)
    elif plan.intent == "compare_bgc":
        result = execute_bgc_compare(connection, plan)
    elif plan.intent == "trajectory":
        result = execute_trajectory(connection, plan)
    elif plan.intent == "profiles":
        result = execute_profiles(connection, plan)
    else:
        result = execute_summary(connection, plan)

    result["intent"] = plan.intent
    result["parameter"] = plan.parameter
    result["retrieval"] = retrieval
    result["answer"] = craft_answer(plan, result, retrieval)
    if openai_service and getattr(openai_service, "enabled", False):
        try:
            ai_answer = openai_service.generate_answer(
                question=question,
                result=result,
                retrieval=retrieval,
            )
        except Exception:
            ai_answer = None
        if ai_answer:
            result["answer"] = ai_answer
            answer_source = provider_name
    result["llm"] = {
        "provider": provider_name if openai_service and getattr(openai_service, "enabled", False) else "local-fallback",
        "plan_source": plan_source,
        "answer_source": answer_source,
        "model": getattr(openai_service, "model", None) if openai_service and getattr(openai_service, "enabled", False) else None,
    }
    return result


def craft_answer(
    plan: QueryPlan, result: dict[str, Any], retrieval: list[dict[str, Any]]
) -> str:
    if plan.intent == "nearest_floats":
        closest = result["rows"][0] if result["rows"] else None
        if closest is None:
            return "I could not find any active floats in the current catalog."
        bgc_text = "BGC-enabled" if closest["is_bgc"] else "core"
        return (
            f"The closest platform is float {closest['wmo']} in the {closest['region']} at "
            f"{closest['distance_km']} km from the selected point. It is a {bgc_text} float."
        )
    if plan.intent == "small_talk":
        return result["summary"]
    if plan.intent == "explanation":
        return result["summary"]
    if plan.intent == "compare_bgc":
        months = len(result["series"])
        region_text = plan.region or "the current search area"
        return (
            f"I compared oxygen, chlorophyll, nitrate, and backscatter over {months} monthly bins for "
            f"{region_text}. Use the chart to spot seasonal swings and BGC-rich periods."
        )
    if plan.intent == "profiles":
        count = len(result["profiles"])
        region_text = plan.region or "the selected waters"
        return (
            f"I pulled {count} {plan.parameter} profiles from {region_text}. "
            f"The deepest samples reach 1000 m, so you can compare surface structure and thermocline behavior."
        )
    if plan.intent == "trajectory":
        return "I grouped float trajectories so you can inspect drift pathways and revisit corridors across the basin."
    top_doc = retrieval[0]["title"] if retrieval else "the catalog"
    return f"I summarized the matching profiles and grounded the answer with metadata from {top_doc}."


def dashboard_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    counts = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM floats) AS floats,
            (SELECT COUNT(*) FROM profiles) AS profiles,
            (SELECT COUNT(*) FROM measurements) AS samples,
            (SELECT COUNT(*) FROM profiles WHERE profile_type = 'BGC') AS bgc_profiles
        """
    ).fetchone()
    latest = connection.execute(
        """
        SELECT MAX(date(observed_at)) AS latest,
               AVG(surface_temperature_c) AS avg_temp,
               AVG(surface_salinity_psu) AS avg_salinity
        FROM profiles
        """
    ).fetchone()
    regions = connection.execute(
        """
        SELECT region, COUNT(*) AS total_profiles, AVG(surface_temperature_c) AS avg_temp
        FROM profiles
        GROUP BY region
        ORDER BY total_profiles DESC
        """
    ).fetchall()
    return {
        "counts": {
            "floats": counts["floats"],
            "profiles": counts["profiles"],
            "samples": counts["samples"],
            "bgc_profiles": counts["bgc_profiles"],
        },
        "latest_date": latest["latest"],
        "avg_temp": round(latest["avg_temp"], 2),
        "avg_salinity": round(latest["avg_salinity"], 2),
        "regions": [
            {
                "region": row["region"],
                "profiles": row["total_profiles"],
                "avg_temp": round(row["avg_temp"], 2),
            }
            for row in regions
        ],
        "prompt_examples": [
            "Show me salinity profiles near the equator in March 2023",
            "Compare BGC parameters in the Arabian Sea for the last 6 months",
            "What are the nearest ARGO floats to 12.5, 72.4?",
        ],
    }


def map_payload(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT wmo, region, is_bgc, last_latitude, last_longitude, last_reported_at
        FROM floats
        ORDER BY wmo ASC
        """
    ).fetchall()
    recent_profiles = connection.execute(
        """
        SELECT p.profile_code, p.region, p.observed_at, p.latitude, p.longitude, f.wmo
        FROM profiles p
        JOIN floats f ON f.id = p.float_id
        ORDER BY datetime(p.observed_at) DESC
        LIMIT 18
        """
    ).fetchall()
    return {
        "floats": [
            {
                "wmo": row["wmo"],
                "region": row["region"],
                "is_bgc": bool(row["is_bgc"]),
                "latitude": row["last_latitude"],
                "longitude": row["last_longitude"],
                "last_reported_at": row["last_reported_at"],
            }
            for row in rows
        ],
        "recent_profiles": [
            {
                "profile_code": row["profile_code"],
                "wmo": row["wmo"],
                "region": row["region"],
                "observed_at": row["observed_at"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            }
            for row in recent_profiles
        ],
    }
