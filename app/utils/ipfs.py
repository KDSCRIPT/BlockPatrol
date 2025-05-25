import os
import requests
from dotenv import load_dotenv

load_dotenv()

# IPFS API configuration
IPFS_API_URL = os.getenv("IPFS_API_URL", "http://127.0.0.1:5001")

class IPFSClient:
    def __init__(self, api_url=IPFS_API_URL):
        self.api_url = api_url

    def _make_request(self, endpoint, method='post', **kwargs):
        url = f"{self.api_url}/api/v0/{endpoint}"
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def add_file(self, file_content, filename, pin=True):
        """Add a file to IPFS and return its hash."""
        files = {'file': (filename, file_content)}
        params = {'pin': 'true' if pin else 'false'}
        response = self._make_request('add', files=files, params=params)
        return response.json()['Hash']

    def pin_add(self, hash_value):
        """Pin a file in IPFS by its hash."""
        params = {'arg': hash_value}
        response = self._make_request('pin/add', params=params)
        return response.json()

    def cat(self, hash_value):
        """Retrieve content from IPFS by its hash."""
        params = {'arg': hash_value}
        response = self._make_request('cat', params=params)
        return response.content

def store_file_in_ipfs(file_content, filename):
    """Store a file in IPFS and return its hash."""
    try:
        # Connect to IPFS
        client = IPFSClient()
        
        # Add file to IPFS with pinning
        file_hash = client.add_file(file_content, filename, pin=True)
        
        # Explicitly pin the file to make sure it appears in IPFS Desktop
        pin_result = client.pin_add(file_hash)
        
        return {
            "success": True,
            "ipfs_hash": file_hash,
            "ipfs_path": f"/ipfs/{file_hash}",
            "local_gateway_url": f"http://localhost:8080/ipfs/{file_hash}",
            "public_gateway_url": f"https://ipfs.io/ipfs/{file_hash}"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Could not connect to IPFS daemon. Please make sure IPFS Desktop is running."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        } 