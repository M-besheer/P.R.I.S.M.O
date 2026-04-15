from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool  # <--- NEW IMPORT

from Backend.main import app
from Backend.database import get_db, Base

# 1. Setup an IN-MEMORY SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# Tell SQLAlchemy to use a single connection for the whole test (StaticPool)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # <--- NEW ARGUMENT
)
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

    post_res = client.post("/projects/", json=new_project)
    assert post_res.status_code == 200

    get_res = client.get("/projects/")
    assert len(get_res.json()) == 1
    assert get_res.json()[0]["name"] == "CI Test Project"