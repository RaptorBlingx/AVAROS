"""PREVENTION core init — Keycloak auth BYPASSED for AVAROS development.

This file replaces /core/__init__.py via Docker volume mount.
It loads addons and initializes data WITHOUT requiring Keycloak.
"""

import urllib
from urllib import parse
from flask import Flask

from core.api.graphql.urls import *
from core.utils.datasources.mongo import mongo_utils
from core.utils.initialization import initialization_util
from core.initialization import Initialization, DataLoad
from flask import request, jsonify
from functools import wraps
from flask_pymongo import PyMongo
import os
from core.services.errors.prevention_errors import PreventionGraphQLView
from mongoengine import connect

app = Flask(__name__)

addons = os.environ.get("ADDONS")

app.config["MONGO_URI"] = (
    f"mongodb://{mongo_utils.mongo_username}:"
    f"{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
    f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}/"
)

mongo = PyMongo(app)

connect(
    host=(
        f"mongodb://{mongo_utils.mongo_username}:"
        f"{urllib.parse.quote_plus(mongo_utils.mongo_pass)}"
        f"@{mongo_utils.mongo_host}:{int(mongo_utils.mongo_port)}"
        f"/wasabi?authSource=admin"
    ),
)

# Load addons
initialization_util.load_addons(addons)

print("[PREVENTION] Initializing data (auth bypassed)")
initialization_util.run_all_functions(DataLoad, "clean_data")
initialization_util.run_all_functions(DataLoad, "load_data")
initialization_util.run_all_functions(Initialization, "init_data")
print("[PREVENTION] Initialization complete")


# No-op auth decorator — bypasses Keycloak
def require_keycloak_token(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        return view_function(*args, **kwargs)
    return decorated_function


# GraphQL endpoint (no auth required)
app.add_url_rule(
    "/graphql",
    view_func=PreventionGraphQLView.as_view(
        "graphql", schema=schema, graphiql=True,
    ),
)


@app.route("/")
def index():
    return jsonify({"status": "ok", "auth": "bypassed"})
