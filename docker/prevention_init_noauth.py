"""
PREVENTION core — no-auth overlay for development.

Drop-in replacement for core/__init__.py that removes Keycloak auth.
Mounted as /core/__init__.py in the Docker container via volume.
"""

import os
import urllib
from urllib import parse

from flask import Flask, Response
from flask_pymongo import PyMongo
from mongoengine import connect
from graphql import print_schema

from core.api.graphql.urls import *  # noqa: F401,F403  (imports schema)
from core.utils.datasources.mongo import mongo_utils
from core.utils.initialization import initialization_util
from core.initialization import Initialization, DataLoad
from core.services.errors.prevention_errors import PreventionGraphQLView

app = Flask(__name__)

addons = os.environ.get("ADDONS")

app.config["MONGO_URI"] = (
    f"mongodb://{mongo_utils.mongo_username}"
    f":{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
    f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}/"
)

mongo = PyMongo(app)

connect(
    host=(
        f"mongodb://{mongo_utils.mongo_username}"
        f":{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
        f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}"
        f"/wasabi?authSource=admin"
    ),
)

# Load addons
initialization_util.load_addons(addons)

print("Initializing data")
initialization_util.run_all_functions(DataLoad, "clean_data")
initialization_util.run_all_functions(DataLoad, "load_data")
initialization_util.run_all_functions(Initialization, "init_data")


# Routes WITHOUT Keycloak auth
@app.route("/", methods=["GET"])
def home():
    return "PREVENTION Platform — AVAROS (Auth Disabled)"


@app.route("/graphql", methods=["POST", "GET"])
def graphql():
    return PreventionGraphQLView.as_view(
        "graphql", schema=schema, graphiql=True,  # noqa: F405
    )()


@app.route("/schema")
def schema_view():
    schema_str = print_schema(schema)  # noqa: F405
    return Response(schema_str, mimetype="text/plain")
