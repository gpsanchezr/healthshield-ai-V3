import pytest
@pytest.fixture(autouse=True)
def no_db_by_default():
    pass
