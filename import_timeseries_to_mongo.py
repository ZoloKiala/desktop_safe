from pymongo import MongoClient
import pandas as pd
from pathlib import Path
import os
from cred import get_credentials

# -------------------------
# Config
# -------------------------
DB_NAME = "timeseries"
COLLECTION_NAME = "TSValues"
BATCH_SIZE = 50_000
TOTAL_DOCS = 50_000

def insert_csv_in_chunks(csv_path):
    total_inserted = 0

    for df in pd.read_csv(csv_path, chunksize=BATCH_SIZE):
        # Ensure correct types
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df["SeriesId"] = df["SeriesId"].astype(str)
        df["value"] = df["value"].astype(float)

        # Build list of Mongo documents
        docs = [
            {
                "Timestamp": row.date.to_pydatetime(),
                "Metadata": row.SeriesId,
                "Value": row.value
            }
            for row in df.itertuples(index=False)
        ]

        if docs:
            collection.insert_many(docs, ordered=False)
            total_inserted += len(docs)

        print(f"Inserted {len(docs)} documents (total: {total_inserted})")

    return total_inserted


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":

    # -------------------------
    # INPUT
    # -------------------------
    creds = get_credentials("MONGO", r"C:\Users\z.kiala\Documents\destop_app\secrets.toml")
    path = Path(r"C:\Users\z.kiala\Documents\destop_app\output\populate")

    # -------------------------
    # Mongo connection
    # -------------------------
    client = MongoClient(creds.uri)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    total=0

    if path.is_file():
        total += insert_csv_in_chunks(path)
        print(f"Total inserted: {total}")
    elif path.is_dir():
        for file in os.listdir(path):
            total += insert_csv_in_chunks(os.path.join(path, file))
            print(f"Total inserted: {total}")
    else:
        print('Path does not exist')
