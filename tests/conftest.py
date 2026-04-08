import pytest

@pytest.fixture
def sample_destination_data():
    return {
        "id": "test-dest",
        "name": "Test",
        "country": "Spain",
        "description": "Test description",
        "source": "test",
    }
