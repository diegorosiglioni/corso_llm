"""The contract of the front-end: frontend/backend-openapi.json is the OpenAPI of the back-end.

If the back-end changes, regenerate the file with UPDATE_CONTRACT=1 on this test and check the
page against the new document (the Node test contract.test.mjs controls requests and fields).
"""

import json
import os
from pathlib import Path

from backend.api import create_app
from backend.db import create_db_engine
from backend.store import ChatStore

CONTRACT = Path(__file__).parent.parent / "frontend" / "backend-openapi.json"


def generated_openapi() -> dict:
    engine = create_db_engine("sqlite://")  # the document does not read the database
    try:
        return create_app(store=ChatStore(engine), agent=None).openapi()
    finally:
        engine.dispose()


def test_contract_is_the_openapi_of_the_backend():  # CA-82
    document = generated_openapi()
    if os.environ.get("UPDATE_CONTRACT") == "1":
        CONTRACT.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == document, (
        "frontend/backend-openapi.json non coincide con l'OpenAPI del back-end: rigeneralo con "
        "UPDATE_CONTRACT=1 e controlla la pagina"
    )
