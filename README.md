# P.R.I.S.M.O
Personal Routines &amp; Integrated System Managing Observer

```
P.R.I.S.M.O/
├── backend/               <-- The "Brain" (FastAPI server, Database, AI eventually)
│   ├── database.py        <-- Connects to SQLite
│   ├── models.py          <-- Defines how a "Project" looks in the database
│   ├── main.py            <-- The API routes (GET, POST)
│   └── requirements.txt
├── frontend/              <-- The "Face" (Your existing PySide6 code goes here later)
└── README.md
```
to run backend:
```
uvicorn main:app --reload
```