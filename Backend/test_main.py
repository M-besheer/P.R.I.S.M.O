from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from Backend.main import app
from Backend.database import get_db, Base

# 1. Setup an IN-MEMORY SQLite database (it only exists in RAM during the test)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the temporary database
Base.metadata.create_all(bind=engine)


# 2. Tell FastAPI to use this fake database instead of the real one
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# 3. Initialize the Test Client
client = TestClient(app)


# --- THE TESTS ---

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200


def test_create_and_get_project():
    new_project = {"name": "CI Test Project", "path": "C:/test/fake/path"}

    # This will now work 1,000 times in a row because the DB is wiped every time!
    post_res = client.post("/projects/", json=new_project)
    assert post_res.status_code == 200

    get_res = client.get("/projects/")
    assert len(get_res.json()) == 1
    assert get_res.json()[0]["name"] == "CI Test Project"