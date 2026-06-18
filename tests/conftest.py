import pytest


collect_ignore = [
    "test_loaders_reports.py",
    "test_ml.py",
]


@pytest.fixture(autouse=True)
def no_db_by_default():
    pass
