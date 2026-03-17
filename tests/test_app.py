from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from app.database import connect
from app.ingest import bootstrap_database
from app.query_engine import dashboard_summary, run_query


class OceanAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        bootstrap_database(self.db_path, reset=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_dashboard_summary_has_seeded_counts(self) -> None:
        with closing(connect(self.db_path)) as connection:
            summary = dashboard_summary(connection)
        self.assertGreater(summary["counts"]["floats"], 0)
        self.assertGreater(summary["counts"]["profiles"], 0)

    def test_profile_query_returns_series(self) -> None:
        with closing(connect(self.db_path)) as connection:
            result = run_query(
                connection,
                "Show me salinity profiles near the equator in March 2023",
            )
        self.assertEqual(result["intent"], "profiles")
        self.assertTrue(result["profiles"])
        self.assertTrue(result["profiles"][0]["series"])

    def test_nearest_query_uses_coordinates(self) -> None:
        with closing(connect(self.db_path)) as connection:
            result = run_query(connection, "What are the nearest ARGO floats to 12.5, 72.4?")
        self.assertEqual(result["intent"], "nearest_floats")
        self.assertEqual(len(result["rows"]), 5)

    def test_explanation_query_returns_glossary_answer(self) -> None:
        with closing(connect(self.db_path)) as connection:
            result = run_query(connection, "What is salinity?")
        self.assertEqual(result["intent"], "explanation")
        self.assertEqual(result["kind"], "explanation")
        self.assertIn("dissolved salt", result["answer"].lower())

    def test_small_talk_does_not_trigger_profile_query(self) -> None:
        with closing(connect(self.db_path)) as connection:
            result = run_query(connection, "hi")
        self.assertEqual(result["intent"], "small_talk")
        self.assertEqual(result["kind"], "small_talk")
        self.assertIn("argo", result["answer"].lower())

    def test_query_can_use_ai_service_stub(self) -> None:
        class StubAIService:
            enabled = True
            model = "stub-model"

            def plan_query(self, **_: object) -> dict[str, object]:
                return {
                    "intent": "nearest_floats",
                    "parameter": "temperature",
                    "region": "",
                    "start_date": "",
                    "end_date": "",
                    "use_lat_range": False,
                    "lat_min": 0.0,
                    "lat_max": 0.0,
                    "use_lon_range": False,
                    "lon_min": 0.0,
                    "lon_max": 0.0,
                    "use_point": True,
                    "point_lat": 10.0,
                    "point_lon": 70.0,
                    "rationale": "stub",
                }

            def generate_answer(self, **_: object) -> str:
                return "Stubbed AI answer"

        with closing(connect(self.db_path)) as connection:
            result = run_query(
                connection,
                "Find something near the west coast of India",
                openai_service=StubAIService(),
            )
        self.assertEqual(result["intent"], "nearest_floats")
        self.assertEqual(result["answer"], "Stubbed AI answer")
        self.assertEqual(result["llm"]["plan_source"], "llm")
        self.assertEqual(result["llm"]["answer_source"], "llm")


if __name__ == "__main__":
    unittest.main()
