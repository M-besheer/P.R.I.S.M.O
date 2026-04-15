from fastapi import FastAPI
from Backend import models
from Backend.database import engine

# Import your new routers!
from Backend.routers import projects

# Create the database tables
models.Base.metadata.create_all(bind=engine)

# Initialize the main app
app = FastAPI(title="P.R.I.S.M.O Core API", version="1.0.0")

# Plug the routers into the main app
app.include_router(projects.router)
app.include_router(projects.ide_router)

@app.get("/")
def read_root():
    return {"status": "P.R.I.S.M.O Core is Online. All systems nominal."}