"""Per-user writing defaults and shared administrator integrations."""
import os
from app.models.settings_profile import WorkspacePreference
from app.services.secret_store import get_secret

def read_preferences(db, key):
    row = db.get(WorkspacePreference, key)
    return row.value if row else {}

def write_preferences(db, key, value):
    row = db.get(WorkspacePreference, key)
    if row is None:
        db.add(WorkspacePreference(id=key, value=value))
    else:
        row.value = value
    db.commit()
    return value

def integration_key(db, kind):
    return get_secret(db, "integration:" + kind) or os.environ.get({"tavily":"TAVILY_API_KEY", "github":"GITHUB_TOKEN"}[kind], "")
