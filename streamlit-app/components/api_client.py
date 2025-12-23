import requests
import streamlit as st
from typing import Dict, Any, Optional, List

class VRPAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def check_health(self) -> bool:
        """Check if the FastAPI backend is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get available adapters and solvers"""
        try:
            response = requests.get(f"{self.base_url}/capabilities")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Failed to get capabilities: {e}")
            return {}
    
    def solve_vrp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Solve VRP problem"""
        try:
            response = requests.post(f"{self.base_url}/solver", json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Solver error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_distance_matrix(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate distance matrix"""
        try:
            response = requests.post(f"{self.base_url}/distance-matrix", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Distance matrix error: {e}")
            return {}
    
    def get_osm_pois(self, place: str, key: str, value: str, limit: Optional[int] = 100) -> List[Dict]:
        """Get OSM POIs by place"""
        try:
            params = {"place": place, "key": key, "value": value}
            if limit:
                params["limit"] = limit
            response = requests.get(f"{self.base_url}/osm/pois/by-place", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"OSM data error: {e}")
            return []
    
    def get_benchmarks(self) -> List[Dict]:
        """Get available benchmark datasets"""
        try:
            response = requests.get(f"{self.base_url}/benchmarks")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Benchmarks error: {e}")
            return []
    
    def load_benchmark(self, dataset_name: str) -> Dict[str, Any]:
        """Load a specific benchmark dataset"""
        try:
            response = requests.get(f"{self.base_url}/benchmarks/{dataset_name}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Failed to load benchmark {dataset_name}: {e}")
            return {}

# Global API client instance
@st.cache_resource
def get_api_client():
    return VRPAPIClient()