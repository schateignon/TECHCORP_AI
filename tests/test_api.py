import pytest
import requests

API_URL = "http://192.168.56.10:8000"

def test_health_endpoint():
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_list_open_tickets():
    response = requests.get(f"{API_URL}/tickets/open")
    assert response.status_code == 200
    assert isinstance(response.json(), list)