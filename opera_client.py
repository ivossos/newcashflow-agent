"""
Oracle Opera PMS Integration Client

Handles authentication and rate synchronization with Oracle Opera Cloud.
"""

import json
import logging
import base64
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import urllib.request
import urllib.error
import ssl

logger = logging.getLogger("opera-client")

# Data directory for caching
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class OperaClient:
    """Oracle Opera Cloud API Client for rate management."""

    def __init__(self, config: dict):
        """
        Initialize Opera client.

        Config should contain:
        - opera_url: Opera Cloud API base URL
        - opera_username: API username
        - opera_password: API password
        - opera_hotel_id: Hotel ID in Opera
        - opera_client_id: OAuth client ID
        - opera_client_secret: OAuth client secret
        """
        self.base_url = config.get("opera_url", "").rstrip("/")
        self.username = config.get("opera_username", "")
        self.password = config.get("opera_password", "")
        self.hotel_id = config.get("opera_hotel_id", "")
        self.client_id = config.get("opera_client_id", "")
        self.client_secret = config.get("opera_client_secret", "")
        self.access_token = None
        self.token_expiry = None

        # SSL context for HTTPS
        self.ssl_context = ssl.create_default_context()

    def _get_auth_header(self) -> str:
        """Get basic auth header for token request."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def authenticate(self) -> bool:
        """
        Authenticate with Opera Cloud and get access token.

        Returns:
            True if authentication successful, False otherwise
        """
        if not self.base_url or not self.client_id:
            logger.warning("Opera not configured - using mock mode")
            return False

        # Check if token is still valid
        if self.access_token and self.token_expiry:
            if datetime.now() < self.token_expiry:
                return True

        try:
            token_url = f"{self.base_url}/oauth/v1/tokens"

            data = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password
            }

            request = urllib.request.Request(
                token_url,
                data=json.dumps(data).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self._get_auth_header()
                },
                method="POST"
            )

            with urllib.request.urlopen(request, context=self.ssl_context) as response:
                result = json.loads(response.read().decode())
                self.access_token = result.get("access_token")
                expires_in = result.get("expires_in", 3600)
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info("Successfully authenticated with Opera Cloud")
                return True

        except urllib.error.URLError as e:
            logger.error(f"Opera authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Opera authentication error: {e}")
            return False

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Make authenticated request to Opera API."""
        if not self.authenticate():
            return None

        url = f"{self.base_url}{endpoint}"

        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(data).encode() if data else None,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                    "x-hotelid": self.hotel_id
                },
                method=method
            )

            with urllib.request.urlopen(request, context=self.ssl_context) as response:
                return json.loads(response.read().decode())

        except urllib.error.URLError as e:
            logger.error(f"Opera API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Opera API error: {e}")
            return None

    def get_rate_codes(self) -> list:
        """Get available rate codes from Opera."""
        result = self._make_request("GET", f"/par/v1/hotels/{self.hotel_id}/rateCodes")
        if result:
            return result.get("rateCodes", [])
        return []

    def get_current_rates(self, start_date: str, end_date: str, rate_code: str = "BAR") -> list:
        """
        Get current rates from Opera.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            rate_code: Rate code to fetch (default: BAR - Best Available Rate)

        Returns:
            List of rate records
        """
        endpoint = f"/par/v1/hotels/{self.hotel_id}/rates"
        params = f"?startDate={start_date}&endDate={end_date}&ratePlanCode={rate_code}"

        result = self._make_request("GET", endpoint + params)
        if result:
            return result.get("rates", [])
        return []

    def update_rate(self, date: str, rate_code: str, room_type: str,
                    amount: float, currency: str = "USD") -> bool:
        """
        Update a rate in Opera.

        Args:
            date: Date to update (YYYY-MM-DD)
            rate_code: Rate code (e.g., BAR, RACK)
            room_type: Room type code
            amount: New rate amount
            currency: Currency code

        Returns:
            True if successful
        """
        endpoint = f"/par/v1/hotels/{self.hotel_id}/rates"

        data = {
            "rates": [{
                "ratePlanCode": rate_code,
                "roomType": room_type,
                "start": date,
                "end": date,
                "rateAmounts": [{
                    "adults": 1,
                    "amount": {
                        "amount": amount,
                        "currencyCode": currency
                    }
                }, {
                    "adults": 2,
                    "amount": {
                        "amount": amount,
                        "currencyCode": currency
                    }
                }]
            }]
        }

        result = self._make_request("PUT", endpoint, data)
        return result is not None

    def bulk_update_rates(self, rates: list) -> dict:
        """
        Bulk update rates in Opera.

        Args:
            rates: List of rate updates, each containing:
                - date: YYYY-MM-DD
                - rate_code: Rate code
                - room_type: Room type
                - amount: Rate amount

        Returns:
            Summary of updates
        """
        success_count = 0
        failed_count = 0
        results = []

        for rate in rates:
            success = self.update_rate(
                date=rate["date"],
                rate_code=rate.get("rate_code", "BAR"),
                room_type=rate.get("room_type", "STD"),
                amount=rate["amount"],
                currency=rate.get("currency", "USD")
            )

            results.append({
                "date": rate["date"],
                "amount": rate["amount"],
                "success": success
            })

            if success:
                success_count += 1
            else:
                failed_count += 1

        return {
            "total": len(rates),
            "success": success_count,
            "failed": failed_count,
            "details": results
        }

    def get_inventory(self, start_date: str, end_date: str) -> list:
        """Get room inventory/availability from Opera."""
        endpoint = f"/inv/v1/hotels/{self.hotel_id}/availability"
        params = f"?startDate={start_date}&endDate={end_date}"

        result = self._make_request("GET", endpoint + params)
        if result:
            return result.get("availability", [])
        return []

    def get_occupancy(self, date: str) -> Optional[float]:
        """Get occupancy for a specific date."""
        inventory = self.get_inventory(date, date)
        if inventory:
            total_rooms = inventory[0].get("totalRooms", 0)
            available = inventory[0].get("available", 0)
            if total_rooms > 0:
                return (total_rooms - available) / total_rooms
        return None


class MockOperaClient:
    """Mock Opera client for demo/testing without real Opera connection."""

    def __init__(self, config: dict):
        self.hotel_id = config.get("opera_hotel_id", "CHICAGOL7")
        self.mock_rates = {}
        self._load_mock_data()

    def _load_mock_data(self):
        """Load any previously saved mock rates."""
        mock_file = DATA_DIR / "opera_mock_rates.json"
        if mock_file.exists():
            with open(mock_file, "r") as f:
                self.mock_rates = json.load(f)

    def _save_mock_data(self):
        """Save mock rates to file."""
        mock_file = DATA_DIR / "opera_mock_rates.json"
        with open(mock_file, "w") as f:
            json.dump(self.mock_rates, f, indent=2)

    def authenticate(self) -> bool:
        """Mock authentication always succeeds."""
        return True

    def get_rate_codes(self) -> list:
        """Return mock rate codes."""
        return [
            {"code": "BAR", "name": "Best Available Rate", "description": "Dynamic pricing rate"},
            {"code": "RACK", "name": "Rack Rate", "description": "Standard published rate"},
            {"code": "CORP", "name": "Corporate Rate", "description": "Negotiated corporate rate"},
            {"code": "AAA", "name": "AAA Rate", "description": "AAA member discount"},
            {"code": "GOVT", "name": "Government Rate", "description": "Government per diem rate"}
        ]

    def get_current_rates(self, start_date: str, end_date: str, rate_code: str = "BAR") -> list:
        """Return mock current rates."""
        rates = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            rate_key = f"{date_str}_{rate_code}"

            if rate_key in self.mock_rates:
                amount = self.mock_rates[rate_key]
            else:
                # Generate default rate based on day of week
                base = 189.00
                if current.weekday() >= 4:  # Fri-Sun
                    base *= 1.20
                amount = base

            rates.append({
                "date": date_str,
                "ratePlanCode": rate_code,
                "roomType": "STD",
                "amount": round(amount, 2),
                "currency": "USD"
            })

            current += timedelta(days=1)

        return rates

    def update_rate(self, date: str, rate_code: str, room_type: str,
                    amount: float, currency: str = "USD") -> bool:
        """Update mock rate."""
        rate_key = f"{date}_{rate_code}"
        self.mock_rates[rate_key] = amount
        self._save_mock_data()
        return True

    def bulk_update_rates(self, rates: list) -> dict:
        """Bulk update mock rates."""
        for rate in rates:
            rate_key = f"{rate['date']}_{rate.get('rate_code', 'BAR')}"
            self.mock_rates[rate_key] = rate["amount"]

        self._save_mock_data()

        return {
            "total": len(rates),
            "success": len(rates),
            "failed": 0,
            "details": [{"date": r["date"], "amount": r["amount"], "success": True} for r in rates]
        }

    def get_inventory(self, start_date: str, end_date: str) -> list:
        """Return mock inventory."""
        inventory = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            # Simulate varying occupancy
            import random
            total_rooms = 250
            occupancy = random.uniform(0.65, 0.90)
            available = int(total_rooms * (1 - occupancy))

            inventory.append({
                "date": current.strftime("%Y-%m-%d"),
                "totalRooms": total_rooms,
                "available": available,
                "occupied": total_rooms - available,
                "occupancy": round(occupancy * 100, 1)
            })

            current += timedelta(days=1)

        return inventory

    def get_occupancy(self, date: str) -> float:
        """Return mock occupancy."""
        import random
        return random.uniform(0.65, 0.90)


def get_opera_client(config: dict):
    """
    Factory function to get appropriate Opera client.

    Returns MockOperaClient if Opera is not configured,
    otherwise returns real OperaClient.
    """
    if config.get("opera_url") and config.get("opera_client_id"):
        return OperaClient(config)
    else:
        logger.info("Opera not configured - using mock client")
        return MockOperaClient(config)
