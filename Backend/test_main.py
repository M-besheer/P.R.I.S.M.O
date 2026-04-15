from fastapi.testclient import TestClient
from Backend.main import app

# Create a fake client to talk to our API
client = TestClient(app)


def test_read_root():
    """Test if the API is online"""
    response = client.get("/")
    assert response.status_code == 200
    assert "P.R.I.S.M.O Core is Online" in response.json()["status"]


def test_create_and_get_project():
    """Test creating a project and retrieving it"""
    # 1. Create a project
    new_project = {"name": "CI/CD Test Project", "path": "/test/path/new_project/new"}
    response = client.post("/projects/", json=new_project)

    assert response.status_code == 200
    assert response.json()["name"] == "CI/CD Test Project"

    # 2. Verify it shows up in the GET request
    get_response = client.get("/projects/")
    assert get_response.status_code == 200

    # Check that our test project is in the returned list
    projects = get_response.json()
    assert any(proj["name"] == "CI/CD Test Project" for proj in projects)