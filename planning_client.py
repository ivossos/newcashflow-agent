#!/usr/bin/env python3
"""
Oracle Planning Cloud (EPBCS) Integration Client

Provides both real API client and mock client for testing.
Handles monthly data loads, actuals fetching, and business rule execution.
"""

import json
import logging
import urllib.request
import urllib.error
import ssl
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("planning-client")

DATA_DIR = Path(__file__).parent / "data"


class PlanningClient:
    """Real Oracle Planning Cloud API Client."""

    def __init__(self, base_url: str, username: str, password: str, application: str):
        """
        Initialize Planning client.

        Args:
            base_url: Planning Cloud URL (e.g., https://planning-xxx.pbcs.us2.oraclecloud.com)
            username: Service account username
            password: Service account password
            application: Planning application name
        """
        self.base_url = base_url.rstrip('/')
        self.application = application
        self.auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.ssl_context = ssl.create_default_context()

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make authenticated request to Planning API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }

        body = json.dumps(data, indent=2).encode() if data else None

        # DEBUG: Log the full request
        logger.info(f"=== PLANNING API REQUEST ===")
        logger.info(f"Method: {method}")
        logger.info(f"URL: {url}")
        if body:
            logger.info(f"Payload:\n{body.decode()}")
        logger.info(f"============================")

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, context=self.ssl_context) as response:
                response_body = response.read().decode()
                logger.info(f"=== PLANNING API RESPONSE ===")
                logger.info(f"Status: {response.status}")
                logger.info(f"Body: {response_body}")
                logger.info(f"=============================")
                return json.loads(response_body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"=== PLANNING API ERROR ===")
            logger.error(f"Status: {e.code}")
            logger.error(f"Reason: {e.reason}")
            logger.error(f"Error Body:\n{error_body}")
            logger.error(f"==========================")
            # Return error details instead of raising
            return {
                "error": True,
                "status_code": e.code,
                "reason": e.reason,
                "error_body": error_body
            }

    def get_application_info(self) -> dict:
        """Get Planning application metadata."""
        endpoint = f"/HyperionPlanning/rest/v3/applications/{self.application}"
        return self._make_request("GET", endpoint)

    def load_data(self, data_records: list[dict], load_method: str = "REPLACE") -> dict:
        """
        Load data into Planning using Import Data Slice REST API.

        Args:
            data_records: List of records with dimension members and amounts
            load_method: REPLACE, ACCUMULATE, or SUBTRACT

        Returns:
            API response with status
        """
        # Get unique accounts and periods
        accounts = sorted(list(set(r["Account"] for r in data_records)))
        periods = sorted(list(set(r["Period"] for r in data_records)))

        # Get POV from first record
        sample = data_records[0]

        # Build POV - simple array of strings in order:
        # Entity, Scenario, Years, Version, Currency, Future1, CostCenter, Region
        # Note: Future1 uses ILvl0Descendants function for dynamic member
        pov = [
            sample.get("Entity", "E501"),
            sample.get("Scenario", "Forecast"),
            sample.get("Years", "FY25"),
            sample.get("Version", "Final"),
            sample.get("Currency", "USD"),
            sample.get("Future1", "No Future1"),
            sample.get("CostCenter", "CC1121"),
            sample.get("Region", "R131")
        ]

        # Build columns - array of arrays (Account members)
        columns = [accounts]

        # Build rows - each row has headers (Period) and data (values matching column order)
        rows = []
        for period in periods:
            # Get data for each account in this period (matching column order)
            data_values = []
            for account in accounts:
                value = 0
                for r in data_records:
                    if r["Account"] == account and r["Period"] == period:
                        value = r["Amount"]
                        break
                data_values.append(value)

            rows.append({
                "headers": [period],
                "data": data_values
            })

        # Build the import payload per Oracle docs
        payload = {
            "aggregateEssbaseData": load_method == "ACCUMULATE",
            "cellNotesOption": "Overwrite",
            "dataGrid": {
                "pov": pov,
                "columns": columns,
                "rows": rows
            }
        }

        # Use importdataslice endpoint with FinPlan plan type
        plantype = "FinPlan"
        endpoint = f"/HyperionPlanning/rest/v3/applications/{self.application}/plantypes/{plantype}/importdataslice"

        # Log the payload being sent
        logger.info(f"Sending import to {self.application}/{plantype}")
        logger.info(f"Periods: {periods}")
        logger.info(f"Accounts: {accounts}")

        result = self._make_request("POST", endpoint, payload)

        # Check if error response
        if result.get("error"):
            return {
                "status": "ERROR",
                "message": f"HTTP {result.get('status_code')}: {result.get('reason')}",
                "error_details": result.get("error_body"),
                "periods": periods,
                "accounts_attempted": accounts,
                "payload_sent": payload
            }

        return {
            "status": "SUCCESS",
            "message": f"Data loaded to {self.application}/{plantype}",
            "periods": periods,
            "accounts_loaded": len(accounts),
            "records_loaded": len(data_records),
            "api_response": result
        }

    def run_business_rule(self, rule_name: str, parameters: Optional[dict] = None) -> dict:
        """
        Execute a Planning business rule.

        Args:
            rule_name: Name of the business rule
            parameters: Runtime prompts/parameters for the rule
        """
        endpoint = f"/HyperionPlanning/rest/v3/applications/{self.application}/jobs"

        job_payload = {
            "jobType": "RULES",
            "jobName": rule_name,
            "parameters": parameters or {}
        }

        return self._make_request("POST", endpoint, job_payload)

    def get_job_status(self, job_id: str) -> dict:
        """Check status of a running job."""
        endpoint = f"/HyperionPlanning/rest/v3/applications/{self.application}/jobs/{job_id}"
        return self._make_request("GET", endpoint)

    def fetch_data(self, pov: dict, rows: list[str], columns: list[str]) -> dict:
        """
        Fetch data from Planning grid using Export Data Slice API.

        Args:
            pov: Point of view dimensions dict (e.g., {"Scenario": "Actual", "Entity": "E501", ...})
            rows: List of Account codes to fetch
            columns: Column dimensions (typically ["Amount"])
        """
        plantype = "FinPlan"
        endpoint = f"/HyperionPlanning/rest/v3/applications/{self.application}/plantypes/{plantype}/exportdataslice"

        # Build grid definition for exportdataslice
        # POV: simple array of strings
        # Order: Entity, Scenario, Years, Version, Currency, Future1, CostCenter, Region
        grid_definition = {
            "pov": [
                pov.get("Entity", "E501"),
                pov.get("Scenario", "Actual"),
                pov.get("Years", "FY25"),
                pov.get("Version", "Final"),
                pov.get("Currency", "USD"),
                pov.get("Future1", "No Future1"),
                pov.get("CostCenter", "CC1121"),
                pov.get("Region", "R131")
            ],
            "columns": [rows],  # Account codes as column
            "rows": [[pov.get("Period", "Jan")]]  # Period as row
        }

        payload = {
            "exportPlanningData": False,
            "gridDefinition": grid_definition
        }

        try:
            result = self._make_request("POST", endpoint, payload)

            # Parse response and extract data
            data_records = []
            if "rows" in result:
                for row in result.get("rows", []):
                    account = row.get("headers", [""])[0] if row.get("headers") else ""
                    values = row.get("data", [])
                    amount = float(values[0]) if values and values[0] else 0

                    data_records.append({
                        "Account": account,
                        "Period": pov.get("Period", "Jan-25"),
                        "Amount": amount,
                        "Entity": pov.get("Entity", "E501"),
                        "Scenario": pov.get("Scenario", "Actual")
                    })

            return {
                "status": "SUCCESS",
                "data": data_records,
                "count": len(data_records)
            }

        except Exception as e:
            logger.error(f"Error fetching data from Planning: {e}")
            return {
                "status": "ERROR",
                "message": str(e),
                "data": [],
                "count": 0
            }


class MockPlanningClient:
    """Mock Planning client for testing without real API connection."""

    def __init__(self, application: str = "CashFlow"):
        self.application = application
        self.data_file = DATA_DIR / "planning_mock_data.json"
        self.job_log_file = DATA_DIR / "planning_job_log.json"
        self._load_mock_data()

    def _load_mock_data(self):
        """Load or initialize mock data."""
        if self.data_file.exists():
            with open(self.data_file) as f:
                self.mock_data = json.load(f)
        else:
            self.mock_data = {
                "actuals": {},
                "forecast": {},
                "budget": {}
            }
            self._save_mock_data()

    def _save_mock_data(self):
        """Persist mock data."""
        with open(self.data_file, "w") as f:
            json.dump(self.mock_data, f, indent=2)

    def _log_job(self, job_type: str, job_name: str, status: str, details: dict):
        """Log job execution."""
        jobs = []
        if self.job_log_file.exists():
            with open(self.job_log_file) as f:
                jobs = json.load(f)

        jobs.append({
            "job_id": f"JOB_{len(jobs)+1:05d}",
            "job_type": job_type,
            "job_name": job_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })

        with open(self.job_log_file, "w") as f:
            json.dump(jobs, f, indent=2)

        return jobs[-1]

    def get_application_info(self) -> dict:
        """Get mock application info."""
        return {
            "name": self.application,
            "type": "EPBCS",
            "status": "AVAILABLE",
            "dimensions": [
                "Account", "Entity", "Scenario", "Version",
                "Period", "Years", "Currency", "CostCenter", "Region"
            ],
            "plan_types": ["Plan1", "Plan2"]
        }

    def load_data(self, data_records: list[dict], load_method: str = "REPLACE") -> dict:
        """
        Mock data load - stores in local JSON.

        Args:
            data_records: Records to load
            load_method: REPLACE or ACCUMULATE
        """
        scenario = data_records[0].get("Scenario", "Forecast") if data_records else "Forecast"

        if load_method == "REPLACE":
            self.mock_data[scenario.lower()] = {}

        records_loaded = 0
        for record in data_records:
            key = f"{record.get('Entity', 'E501')}_{record.get('Account', '400000')}_{record.get('Period', 'Jan-25')}"

            if scenario.lower() not in self.mock_data:
                self.mock_data[scenario.lower()] = {}

            if load_method == "ACCUMULATE" and key in self.mock_data[scenario.lower()]:
                self.mock_data[scenario.lower()][key]["Amount"] += record.get("Amount", 0)
            else:
                self.mock_data[scenario.lower()][key] = record

            records_loaded += 1

        self._save_mock_data()

        job = self._log_job(
            "DATARULE",
            f"CashFlowLoad_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "COMPLETED",
            {"records_loaded": records_loaded, "load_method": load_method}
        )

        return {
            "status": "COMPLETED",
            "job_id": job["job_id"],
            "records_loaded": records_loaded,
            "message": f"Successfully loaded {records_loaded} records to {self.application}"
        }

    def run_business_rule(self, rule_name: str, parameters: Optional[dict] = None) -> dict:
        """Mock business rule execution."""
        job = self._log_job(
            "RULES",
            rule_name,
            "COMPLETED",
            {"parameters": parameters or {}}
        )

        return {
            "status": "COMPLETED",
            "job_id": job["job_id"],
            "rule_name": rule_name,
            "message": f"Successfully executed rule: {rule_name}"
        }

    def get_job_status(self, job_id: str) -> dict:
        """Get mock job status."""
        if self.job_log_file.exists():
            with open(self.job_log_file) as f:
                jobs = json.load(f)
                for job in jobs:
                    if job["job_id"] == job_id:
                        return job

        return {"status": "NOT_FOUND", "job_id": job_id}

    def fetch_data(self, pov: dict, rows: list[str], columns: list[str]) -> dict:
        """Fetch mock data matching POV."""
        scenario = pov.get("Scenario", "Forecast").lower()
        entity = pov.get("Entity", "E501")

        results = []
        if scenario in self.mock_data:
            for key, record in self.mock_data[scenario].items():
                if record.get("Entity") == entity:
                    results.append(record)

        return {
            "pov": pov,
            "data": results,
            "count": len(results)
        }


def get_planning_client(config: dict = None):
    """
    Factory function to get appropriate Planning client.

    Reads configuration from environment variables first, then falls back to config dict.
    Returns MockPlanningClient if Planning is not configured or PLANNING_MOCK_MODE is true.
    """
    config = config or {}

    # Environment variables take precedence over config
    planning_url = os.getenv("PLANNING_URL") or config.get("planning_url")
    planning_username = os.getenv("PLANNING_USERNAME") or config.get("planning_username")
    planning_password = os.getenv("PLANNING_PASSWORD") or config.get("planning_password")
    planning_app = os.getenv("PLANNING_APPLICATION") or config.get("planning_application", "PlanApp")
    mock_mode = os.getenv("PLANNING_MOCK_MODE", "false").lower() == "true"

    if mock_mode:
        logger.info("Planning mock mode enabled via environment")
        return MockPlanningClient(application=planning_app)

    if planning_url and planning_username and planning_password:
        logger.info(f"Using real Planning client for {planning_url}")
        return PlanningClient(
            base_url=planning_url,
            username=planning_username,
            password=planning_password,
            application=planning_app
        )
    else:
        logger.info("Planning not configured, using mock client")
        return MockPlanningClient(application=planning_app)
