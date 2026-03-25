"""
AVAROS addon data loader.

Loads manufacturing KPI JSON files (exported by RENERYO data-sync pipeline)
into MongoDB for PREVENTION analysis.
"""

import json
import os
import urllib.parse

import pandas as pd
from pymongo import MongoClient

from core.initialization import DataLoad
from core.utils.datasources.mongo import mongo_utils


class AvarosDataLoad(DataLoad):

    def __init__(self):
        project_name = "avaros"
        self.data_path = os.path.join(os.getcwd(), "addons", project_name, "data")
        self.datasources = [
            {"name": "energy_metrics", "file": "energy_metrics.json",
             "identifier": "id", "date_column": "timestamp"},
            {"name": "production_metrics", "file": "production_metrics.json",
             "identifier": "id", "date_column": "timestamp"},
            {"name": "material_metrics", "file": "material_metrics.json",
             "identifier": "id", "date_column": "timestamp"},
            {"name": "carbon_metrics", "file": "carbon_metrics.json",
             "identifier": "id", "date_column": "timestamp"},
            {"name": "supplier_metrics", "file": "supplier_metrics.json",
             "identifier": "id", "date_column": "timestamp"},
        ]

    def clean_data(self):
        for ds in self.datasources:
            mongo_utils.drop_collection("init_data", ds["name"])

    def load_data(self):
        client = MongoClient(
            f"mongodb://{mongo_utils.mongo_username}"
            f":{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
            f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}/",
        )
        db = client["init_data"]

        for ds in self.datasources:
            file_path = os.path.join(self.data_path, ds["file"])
            if not os.path.exists(file_path):
                print(f"[AVAROS] Skipping {ds['file']}: not found at {file_path}")
                continue

            with open(file_path, encoding="utf-8") as f:
                records = json.load(f)

            if not records:
                print(f"[AVAROS] Skipping {ds['file']}: empty")
                continue

            df = pd.DataFrame(records)
            df = df.drop_duplicates(subset=ds["identifier"], keep="first")
            df = df.dropna(how="all")
            if ds["date_column"] in df.columns:
                df = df.sort_values(by=ds["date_column"])

            col = db[ds["name"]]
            col.create_index(ds["identifier"], unique=True)
            data = df.to_dict(orient="records")
            col.insert_many(data)
            print(f"[AVAROS] Loaded {len(data)} records into {ds['name']}")
