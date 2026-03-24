from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

from cred import get_credentials


DEFAULT_MONGO_DB_NAME = "timeseries"
DEFAULT_MONGO_COLLECTION_NAME = "TSValues"
DEFAULT_MONGO_PROFILE = "populate_mongo_iwmi"
DEFAULT_BATCH_SIZE = 50_000


def resolve_mongo_uri(
    *,
    mongo_uri: str | None = None,
    secrets_file: str | Path | None = None,
    profile: str = DEFAULT_MONGO_PROFILE,
) -> str:
    if mongo_uri and str(mongo_uri).strip():
        return str(mongo_uri).strip()

    creds = get_credentials(profile, secrets_file)
    if not getattr(creds, "uri", None):
        raise ValueError(f"No Mongo URI found for profile: {profile}")

    return str(creds.uri).strip()


def insert_csv_in_chunks(
    *,
    csv_path: str | Path,
    mongo_uri: str,
    db_name: str = DEFAULT_MONGO_DB_NAME,
    collection_name: str = DEFAULT_MONGO_COLLECTION_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Mongo source CSV not found: {csv_path}")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    total_inserted = 0

    try:
        for df in pd.read_csv(csv_path, chunksize=batch_size):
            required = {"date", "SeriesId", "value"}
            missing = required - set(df.columns)
            if missing:
                raise ValueError(
                    "Mongo source CSV is missing required columns: "
                    + ", ".join(sorted(missing))
                )

            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
            df["SeriesId"] = df["SeriesId"].astype(str)
            df["value"] = pd.to_numeric(df["value"], errors="coerce")

            df = df.dropna(subset=["date", "SeriesId", "value"]).copy()

            docs = [
                {
                    "Timestamp": row.date.to_pydatetime(),
                    "Metadata": row.SeriesId,
                    "Value": float(row.value),
                }
                for row in df.itertuples(index=False)
            ]

            if docs:
                collection.insert_many(docs, ordered=False)
                total_inserted += len(docs)

        return total_inserted
    finally:
        client.close()


def insert_path_to_mongo(
    *,
    source_path: str | Path,
    mongo_uri: str,
    db_name: str = DEFAULT_MONGO_DB_NAME,
    collection_name: str = DEFAULT_MONGO_COLLECTION_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[int, list[Path]]:
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Mongo source path does not exist: {source_path}")

    inserted_total = 0
    processed_files: list[Path] = []

    if source_path.is_file():
        inserted_total += insert_csv_in_chunks(
            csv_path=source_path,
            mongo_uri=mongo_uri,
            db_name=db_name,
            collection_name=collection_name,
            batch_size=batch_size,
        )
        processed_files.append(source_path)
        return inserted_total, processed_files

    if source_path.is_dir():
        csv_files = sorted(
            p for p in source_path.iterdir()
            if p.is_file() and p.suffix.lower() == ".csv"
        )
        if not csv_files:
            raise ValueError(f"No CSV files found in folder: {source_path}")

        for file_path in csv_files:
            inserted_total += insert_csv_in_chunks(
                csv_path=file_path,
                mongo_uri=mongo_uri,
                db_name=db_name,
                collection_name=collection_name,
                batch_size=batch_size,
            )
            processed_files.append(file_path)

        return inserted_total, processed_files

    raise ValueError(f"Unsupported Mongo source path: {source_path}")