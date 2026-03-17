#!/usr/bin/env python3
"""Entry point for the ARGO Ocean Assistant demo."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.ingest import bootstrap_database, ingest_netcdf_files
from app.openai_service import LLMService
from app.server import run_server


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run the ARGO Ocean Assistant portfolio demo."
    )
    parser.add_argument(
        "--db-path",
        default=str(root / "data" / "argo_ocean_assistant.sqlite3"),
        help="SQLite database path.",
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="Bind host.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8765")),
        help="Bind port.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Rebuild the database before starting the server.",
    )
    parser.add_argument(
        "--ingest-netcdf",
        nargs="*",
        default=[],
        help="Optional NetCDF files to ingest after demo data is seeded.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        if os.environ.get("HF_TOKEN"):
            provider = "huggingface"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("OLLAMA_MODEL"):
            provider = "ollama"
        else:
            provider = "local"

    if provider == "huggingface":
        llm_service = LLMService(
            provider="huggingface",
            api_key=os.environ.get("HF_TOKEN"),
            model=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", "low"),
            base_url=os.environ.get("HF_BASE_URL", "https://router.huggingface.co/v1"),
        )
    elif provider == "openai":
        llm_service = LLMService(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY"),
            model=os.environ.get("LLM_MODEL", os.environ.get("OPENAI_MODEL", "gpt-5-mini")),
            reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", os.environ.get("OPENAI_REASONING_EFFORT", "low")),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    elif provider == "ollama":
        llm_service = LLMService(
            provider="ollama",
            model=os.environ.get("OLLAMA_MODEL", os.environ.get("LLM_MODEL", "gemma3:4b")),
            reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", "low"),
            ollama_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
    else:
        llm_service = LLMService(provider="local")

    bootstrap_database(db_path, reset=args.reset)
    if args.ingest_netcdf:
        ingest_netcdf_files(db_path, [Path(item) for item in args.ingest_netcdf])

    run_server(host=args.host, port=args.port, db_path=db_path, openai_service=llm_service)


if __name__ == "__main__":
    main()
