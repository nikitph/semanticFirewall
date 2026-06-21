from __future__ import annotations

import pytest

from app.canonicalization import MockCanonicalizer
from app.pipeline import Pipeline
from app.storage import Storage


@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "grounding_firewall_test.db"
    storage = Storage(str(db_path))
    storage.init_db()
    return storage


@pytest.fixture
def pipeline(storage):
    return Pipeline(storage=storage, canonicalizer=MockCanonicalizer())
