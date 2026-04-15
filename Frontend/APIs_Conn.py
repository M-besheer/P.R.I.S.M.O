import requests
from typing import List, Dict, Optional

# The address where your FastAPI backend is running
BASE_URL = "http://127.0.0.1:8000"


class PrismoAPI:
    """
    Centralized API Client for the P.R.I.S.M.O Frontend.
    Handles all HTTP requests to the FastAPI Backend.
    """

    # ==========================================
    # PROJECTS API
    # ==========================================

    @staticmethod
    def get_projects() -> List[Dict]:
        """Fetches all projects from the backend database."""
        try:
            response = requests.get(f"{BASE_URL}/projects/")
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            print("[API Error] Could not connect to Backend. Is Uvicorn running?")
        return []

    @staticmethod
    def create_project(name: str, path: str) -> Optional[Dict]:
        """Sends a new project to the backend to be saved."""
        try:
            payload = {"name": name, "path": path}
            response = requests.post(f"{BASE_URL}/projects/", json=payload)
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            print("[API Error] Connection refused.")
        return None

    @staticmethod
    def update_project(project_id: int, name: str = None, path: str = None, is_active: bool = None) -> Optional[Dict]:
        """Updates specific fields of an existing project."""
        payload = {}
        if name is not None: payload["name"] = name
        if path is not None: payload["path"] = path
        if is_active is not None: payload["is_active"] = is_active

        try:
            response = requests.put(f"{BASE_URL}/projects/{project_id}", json=payload)
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            print("[API Error] Connection refused.")
        return None

    @staticmethod
    def delete_project(project_id: int) -> bool:
        """Deletes a project by its database ID."""
        try:
            response = requests.delete(f"{BASE_URL}/projects/{project_id}")
            return response.status_code == 200
        except requests.ConnectionError:
            print("[API Error] Connection refused.")
            return False

    # ==========================================
    # IDEs API
    # ==========================================

    @staticmethod
    def get_ides() -> List[Dict]:
        """Fetches all saved IDE executable paths."""
        try:
            response = requests.get(f"{BASE_URL}/ides/")
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            pass
        return []

    @staticmethod
    def add_ide(name: str, path: str) -> Optional[Dict]:
        """Saves a new IDE executable path."""
        try:
            payload = {"name": name, "path": path}
            response = requests.post(f"{BASE_URL}/ides/", json=payload)
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            pass
        return None