import os
import re
from pathlib import Path

SCHEMA = os.getenv("TERADATA_DATABASE", "officelunch")
if not re.fullmatch(r"officelunch(?:_[a-z0-9]+)?", SCHEMA):
    raise ValueError("TERADATA_DATABASE must be officelunch or officelunch_<suffix>")
ARTIFACTS = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts"))
FOOD = Path(os.getenv("FOOD_PATH", "/data/food.txt"))
PREFIX = os.getenv("QDRANT_PREFIX", "officelunch")
if not re.fullmatch(r"officelunch(?:_[a-z0-9]+)?", PREFIX):
    raise ValueError("QDRANT_PREFIX must be officelunch or officelunch_<suffix>")


def qclient():
    from qdrant_client import QdrantClient

    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://100.65.210.21:6333"),
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=30,
    )
