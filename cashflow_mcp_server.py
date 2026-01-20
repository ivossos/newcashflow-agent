#!/usr/bin/env python3
"""
Hotel Daily Cash Flow Forecasting MCP Server with Dynamic Pricing

This MCP server provides tools for forecasting and managing hotel daily cash flows,
with a full dynamic pricing engine for revenue optimization.

Tools:
1. generate_daily_forecast - Generate cash flow forecast for specified period
2. get_cash_position - Get current cash position and balances
3. run_scenario - Run what-if scenarios on cash flow
4. validate_forecast - Validate forecast against actuals
5. export_report - Export cash flow reports in various formats
6. optimize_pricing - Calculate optimal room rates using dynamic pricing
7. get_events - Get local events calendar that impact demand
8. get_competitor_rates - Get competitor rate analysis

Dynamic Pricing Factors:
- Occupancy levels (6 tiers from critical_low to sold_out)
- Day of week adjustments (Mon-Sun)
- Seasonality (12 months)
- Lead time (same day to far advance)
- Local events (conventions, sports, festivals, holidays)
- Competitor rate analysis
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path
import random

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Opera PMS Integration
from opera_client import get_opera_client

# Oracle Planning Integration
from planning_client import get_planning_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cashflow-mcp-server")

# Initialize MCP server
server = Server("cashflow-mcp-server")

# Data storage path
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Cash flow categories aligned with Oracle Planning (Account dimension)
# Valid PlanApp level 0 STORE accounts only (not dynamic calc parents)
INFLOW_CATEGORIES = {
    "411110": "Rooms Only",
    "411120": "Retail Web",
    "421100": "Breakfast Food Revenue",
    "421200": "Lunch Food Revenue",
    "421300": "Dinner Food Revenue"
}

OUTFLOW_CATEGORIES = {
    "611240": "State Unemployment Insurance",
    "611350": "Local Other Payroll Tax",
    "611410": "Other Payroll Tax 1",
    "612110": "Other Pay",
    "612510": "Severance Pay",
    "612610": "Sick Pay",
    "612710": "Holiday Pay",
    "710100": "Agency Fees",
    "710110": "Ambience",
    "710120": "Athletic Supplies",
    "710130": "Audit Charges",
    "710140": "Bank Charges",
    "710150": "Banquet Expenses",
    "710220": "Cleaning Supplies",
    "710310": "Credit Card Commissions"
}

# Entity (Hotel) mappings from Planning
ENTITY_MAPPINGS = {
    "E501": {"alias": "501-L7 Chicago Hotel", "parent": "E500", "region": "R131", "cost_center": "CC1121"},
    "E502": {"alias": "502-L7 Chicago Hotel 2", "parent": "E500", "region": "R131", "cost_center": "CC2110"},
    "E503": {"alias": "503-L7 Chicago Hotel 3", "parent": "E500", "region": "R131", "cost_center": None},
    "E101": {"alias": "101-NY Hotel", "parent": "E100", "region": None, "cost_center": None},
    "E102": {"alias": "102-Seattle Hotel", "parent": "E100", "region": None, "cost_center": None},
    "E801": {"alias": "801-SG Hotel 1", "parent": "E800", "region": None, "cost_center": None},
}

# Cost Center (Department) mappings from Planning
COST_CENTER_MAPPINGS = {
    "CC1000": "Rooms",
    "CC1121": "Rooms - Sub",
    "CC2000": "F&B",
    "CC2110": "F&B - Sub",
    "CC2210": "F&B - Sub 2",
    "CC2300": "F&B - Sub 3",
    "CC3000": "Other",
    "CC4000": "Misc",
    "CC9999": "All CostCenters (rollup)"
}

# =============================================================================
# DYNAMIC PRICING ENGINE
# =============================================================================

# Dynamic Pricing Configuration
DYNAMIC_PRICING_CONFIG = {
    "base_rate": 189.00,
    "min_rate": 99.00,
    "max_rate": 449.00,

    # Occupancy-based adjustments
    "occupancy_tiers": {
        "critical_low": {"threshold": 0.30, "adjustment": -0.25},   # <30% = -25%
        "low": {"threshold": 0.50, "adjustment": -0.15},            # 30-50% = -15%
        "moderate": {"threshold": 0.70, "adjustment": 0.0},         # 50-70% = base
        "high": {"threshold": 0.85, "adjustment": 0.15},            # 70-85% = +15%
        "very_high": {"threshold": 0.95, "adjustment": 0.30},       # 85-95% = +30%
        "sold_out": {"threshold": 1.0, "adjustment": 0.50}          # 95%+ = +50%
    },

    # Day of week adjustments
    "day_of_week": {
        0: {"name": "Monday", "adjustment": -0.10},
        1: {"name": "Tuesday", "adjustment": -0.12},
        2: {"name": "Wednesday", "adjustment": -0.05},
        3: {"name": "Thursday", "adjustment": 0.05},
        4: {"name": "Friday", "adjustment": 0.20},
        5: {"name": "Saturday", "adjustment": 0.25},
        6: {"name": "Sunday", "adjustment": 0.0}
    },

    # Lead time adjustments (days before arrival)
    "lead_time": {
        "same_day": {"max_days": 0, "adjustment": 0.30},
        "last_minute": {"max_days": 3, "adjustment": 0.15},
        "short": {"max_days": 7, "adjustment": 0.05},
        "standard": {"max_days": 14, "adjustment": 0.0},
        "advance": {"max_days": 30, "adjustment": -0.05},
        "early_bird": {"max_days": 60, "adjustment": -0.10},
        "far_advance": {"max_days": 365, "adjustment": -0.15}
    },

    # Seasonality adjustments
    "seasonality": {
        1: {"name": "January", "adjustment": -0.20},
        2: {"name": "February", "adjustment": -0.20},
        3: {"name": "March", "adjustment": 0.05},
        4: {"name": "April", "adjustment": 0.10},
        5: {"name": "May", "adjustment": 0.15},
        6: {"name": "June", "adjustment": 0.25},
        7: {"name": "July", "adjustment": 0.30},
        8: {"name": "August", "adjustment": 0.25},
        9: {"name": "September", "adjustment": 0.10},
        10: {"name": "October", "adjustment": 0.15},
        11: {"name": "November", "adjustment": -0.15},
        12: {"name": "December", "adjustment": 0.35}
    },

    # Competitor rate response
    "competitor_response": {
        "undercut_threshold": 0.10,  # Match if competitor is within 10%
        "premium_allowed": 0.15      # Can be up to 15% above market
    }
}

# Chicago Local Events Calendar (sample events for demo)
CHICAGO_EVENTS = {
    # Major conventions and conferences
    "2026-01-20": {"name": "Chicago Auto Show Setup", "impact": 0.15, "type": "convention"},
    "2026-01-21": {"name": "Chicago Auto Show", "impact": 0.40, "type": "convention"},
    "2026-01-22": {"name": "Chicago Auto Show", "impact": 0.40, "type": "convention"},
    "2026-01-23": {"name": "Chicago Auto Show", "impact": 0.40, "type": "convention"},
    "2026-01-24": {"name": "Chicago Auto Show", "impact": 0.45, "type": "convention"},
    "2026-01-25": {"name": "Chicago Auto Show", "impact": 0.45, "type": "convention"},

    "2026-02-14": {"name": "Valentine's Day", "impact": 0.25, "type": "holiday"},

    "2026-03-14": {"name": "St. Patrick's Day Parade", "impact": 0.35, "type": "event"},
    "2026-03-17": {"name": "St. Patrick's Day", "impact": 0.30, "type": "holiday"},

    "2026-04-03": {"name": "NCAA Final Four", "impact": 0.50, "type": "sports"},
    "2026-04-04": {"name": "NCAA Final Four", "impact": 0.55, "type": "sports"},
    "2026-04-05": {"name": "NCAA Championship", "impact": 0.60, "type": "sports"},

    "2026-05-24": {"name": "Memorial Day Weekend", "impact": 0.20, "type": "holiday"},
    "2026-05-25": {"name": "Memorial Day", "impact": 0.15, "type": "holiday"},

    "2026-06-12": {"name": "Chicago Blues Festival", "impact": 0.30, "type": "festival"},
    "2026-06-13": {"name": "Chicago Blues Festival", "impact": 0.35, "type": "festival"},
    "2026-06-14": {"name": "Chicago Blues Festival", "impact": 0.35, "type": "festival"},

    "2026-07-03": {"name": "Independence Day Weekend", "impact": 0.30, "type": "holiday"},
    "2026-07-04": {"name": "Independence Day", "impact": 0.35, "type": "holiday"},

    "2026-08-01": {"name": "Lollapalooza Day 1", "impact": 0.45, "type": "festival"},
    "2026-08-02": {"name": "Lollapalooza Day 2", "impact": 0.50, "type": "festival"},
    "2026-08-03": {"name": "Lollapalooza Day 3", "impact": 0.50, "type": "festival"},
    "2026-08-04": {"name": "Lollapalooza Day 4", "impact": 0.45, "type": "festival"},

    "2026-09-05": {"name": "Labor Day Weekend", "impact": 0.20, "type": "holiday"},
    "2026-09-06": {"name": "Labor Day Weekend", "impact": 0.25, "type": "holiday"},
    "2026-09-07": {"name": "Labor Day", "impact": 0.15, "type": "holiday"},

    "2026-10-11": {"name": "Chicago Marathon", "impact": 0.40, "type": "sports"},
    "2026-10-31": {"name": "Halloween", "impact": 0.15, "type": "holiday"},

    "2026-11-26": {"name": "Thanksgiving", "impact": 0.10, "type": "holiday"},
    "2026-11-27": {"name": "Black Friday", "impact": 0.20, "type": "shopping"},
    "2026-11-28": {"name": "Thanksgiving Weekend", "impact": 0.15, "type": "holiday"},

    "2026-12-24": {"name": "Christmas Eve", "impact": 0.20, "type": "holiday"},
    "2026-12-25": {"name": "Christmas Day", "impact": 0.15, "type": "holiday"},
    "2026-12-31": {"name": "New Year's Eve", "impact": 0.50, "type": "holiday"},
}

# Competitor rates (simulated market data)
COMPETITOR_RATES = {
    "Marriott Downtown": {"base_rate": 199.00, "variance": 0.10},
    "Hilton Chicago": {"base_rate": 209.00, "variance": 0.12},
    "Hyatt Regency": {"base_rate": 195.00, "variance": 0.08},
    "Palmer House": {"base_rate": 185.00, "variance": 0.15},
}


def get_event_impact(date: datetime) -> dict:
    """Get local event impact for a specific date."""
    date_str = date.strftime("%Y-%m-%d")
    if date_str in CHICAGO_EVENTS:
        return CHICAGO_EVENTS[date_str]
    return None


def get_competitor_rates(date: datetime) -> dict:
    """Get simulated competitor rates for a date."""
    rates = {}
    for name, data in COMPETITOR_RATES.items():
        # Add some daily variance
        variance = random.uniform(-data["variance"], data["variance"])

        # Apply day of week adjustment
        dow_adj = DYNAMIC_PRICING_CONFIG["day_of_week"][date.weekday()]["adjustment"]

        # Apply event impact if any
        event = get_event_impact(date)
        event_adj = event["impact"] if event else 0

        rate = data["base_rate"] * (1 + variance + dow_adj + event_adj)
        rates[name] = round(rate, 2)

    return rates


def calculate_dynamic_rate(date: datetime, config: dict, current_occupancy: float = None,
                           lead_days: int = None, include_breakdown: bool = False) -> dict:
    """
    Calculate dynamic room rate based on multiple factors.

    Args:
        date: Target date for pricing
        config: Hotel configuration
        current_occupancy: Current occupancy level (0-1), defaults to projected
        lead_days: Days until arrival, defaults to 0 (same day)
        include_breakdown: Include detailed factor breakdown

    Returns:
        Dictionary with optimized rate and factors
    """
    pricing = DYNAMIC_PRICING_CONFIG
    base_rate = config.get("average_daily_rate", pricing["base_rate"])

    adjustments = {}
    total_adjustment = 0.0

    # 1. Occupancy-based adjustment
    if current_occupancy is None:
        current_occupancy = config.get("average_occupancy", 0.75)

    occ_adjustment = 0.0
    occ_tier = "moderate"
    for tier, data in pricing["occupancy_tiers"].items():
        if current_occupancy <= data["threshold"]:
            occ_adjustment = data["adjustment"]
            occ_tier = tier
            break

    adjustments["occupancy"] = {
        "level": round(current_occupancy * 100, 1),
        "tier": occ_tier,
        "adjustment": occ_adjustment
    }
    total_adjustment += occ_adjustment

    # 2. Day of week adjustment
    dow = date.weekday()
    dow_data = pricing["day_of_week"][dow]
    adjustments["day_of_week"] = {
        "day": dow_data["name"],
        "adjustment": dow_data["adjustment"]
    }
    total_adjustment += dow_data["adjustment"]

    # 3. Seasonality adjustment
    month = date.month
    season_data = pricing["seasonality"][month]
    adjustments["seasonality"] = {
        "month": season_data["name"],
        "adjustment": season_data["adjustment"]
    }
    total_adjustment += season_data["adjustment"]

    # 4. Lead time adjustment
    if lead_days is None:
        lead_days = 0

    lead_adjustment = 0.0
    lead_tier = "same_day"
    for tier, data in pricing["lead_time"].items():
        if lead_days <= data["max_days"]:
            lead_adjustment = data["adjustment"]
            lead_tier = tier
            break

    adjustments["lead_time"] = {
        "days": lead_days,
        "tier": lead_tier,
        "adjustment": lead_adjustment
    }
    total_adjustment += lead_adjustment

    # 5. Local event impact
    event = get_event_impact(date)
    if event:
        adjustments["event"] = {
            "name": event["name"],
            "type": event["type"],
            "adjustment": event["impact"]
        }
        total_adjustment += event["impact"]
    else:
        adjustments["event"] = None

    # 6. Competitor analysis
    competitor_rates = get_competitor_rates(date)
    avg_competitor = sum(competitor_rates.values()) / len(competitor_rates)

    adjustments["competitors"] = {
        "rates": competitor_rates,
        "average": round(avg_competitor, 2)
    }

    # Calculate raw optimized rate
    raw_rate = base_rate * (1 + total_adjustment)

    # Apply min/max bounds
    optimized_rate = max(pricing["min_rate"], min(pricing["max_rate"], raw_rate))

    # Check against competitor average
    if optimized_rate > avg_competitor * (1 + pricing["competitor_response"]["premium_allowed"]):
        # Cap at premium above market
        market_capped_rate = avg_competitor * (1 + pricing["competitor_response"]["premium_allowed"])
        adjustments["market_cap_applied"] = True
        optimized_rate = min(optimized_rate, market_capped_rate)
    else:
        adjustments["market_cap_applied"] = False

    result = {
        "date": date.strftime("%Y-%m-%d"),
        "day_of_week": pricing["day_of_week"][dow]["name"],
        "base_rate": base_rate,
        "optimized_rate": round(optimized_rate, 2),
        "total_adjustment_pct": round(total_adjustment * 100, 1),
        "rate_change": round(optimized_rate - base_rate, 2),
        "competitor_avg": round(avg_competitor, 2),
        "position_vs_market": "above" if optimized_rate > avg_competitor else "below" if optimized_rate < avg_competitor else "at"
    }

    if include_breakdown:
        result["factor_breakdown"] = adjustments

    return result


def calculate_dynamic_inflows(date: datetime, config: dict, occupancy: float = None) -> dict:
    """Calculate daily inflows using dynamic pricing."""
    # Get dynamic rate
    dynamic = calculate_dynamic_rate(date, config, current_occupancy=occupancy)
    dynamic_rate = dynamic["optimized_rate"]

    # Use provided occupancy or adjust based on price elasticity
    if occupancy is None:
        base_occupancy = config.get("average_occupancy", 0.75)
        # Price elasticity: higher prices slightly reduce occupancy
        rate_diff_pct = (dynamic_rate - config["average_daily_rate"]) / config["average_daily_rate"]
        elasticity = -0.3  # 10% price increase = 3% occupancy decrease
        occupancy = base_occupancy * (1 + rate_diff_pct * elasticity)
        occupancy = max(0.20, min(0.98, occupancy))  # Bounds

    # Calculate room revenue with dynamic rate
    room_revenue = config["room_count"] * occupancy * dynamic_rate

    # Add variance for realism
    variance = random.uniform(0.97, 1.03)

    return {
        "411110": round(room_revenue * 0.70 * variance, 2),    # Rooms Only (main)
        "411120": round(room_revenue * 0.30 * variance, 2),    # Retail Web
        "421100": round(room_revenue * 0.15 * variance, 2),    # Breakfast Food
        "421200": round(room_revenue * 0.10 * variance, 2),    # Lunch Food
        "421300": round(room_revenue * 0.10 * variance, 2),    # Dinner Food
        "_dynamic_rate": dynamic_rate,
        "_occupancy": round(occupancy, 3)
    }


def load_hotel_data() -> dict:
    """Load hotel configuration and historical data."""
    config_file = DATA_DIR / "hotel_config.json"
    if config_file.exists():
        with open(config_file, "r") as f:
            return json.load(f)

    # Default hotel configuration - aligned with Oracle Planning (E501 - L7 Chicago Hotel)
    default_config = {
        "hotel_name": "501-L7 Chicago Hotel",
        "entity_id": "E501",
        "region": "R131",
        "region_name": "Illinois",
        "cost_center": "CC1121",
        "scenario": "Actual",
        "version": "Final",
        "currency": "USD",
        "fiscal_year": "FY25",
        "room_count": 250,
        "average_daily_rate": 189.00,
        "average_occupancy": 0.75,
        "opening_cash_balance": 350000.00,
        "minimum_cash_reserve": 75000.00,
        "seasonality": {
            "high_season_months": [6, 7, 8, 12],
            "low_season_months": [1, 2, 11],
            "high_season_multiplier": 1.35,
            "low_season_multiplier": 0.65
        },
        "planning_dimensions": {
            "Account": "400000",
            "Entity": "E501",
            "Scenario": "Actual",
            "Years": "FY25",
            "Period": "YearTotal",
            "Version": "Final",
            "Currency": "USD",
            "Future1": "No Future1",
            "CostCenter": "CC1121",
            "Region": "R131"
        }
    }

    with open(config_file, "w") as f:
        json.dump(default_config, f, indent=2)

    return default_config


def calculate_daily_inflows(date: datetime, config: dict) -> dict:
    """Calculate expected daily cash inflows using Planning account codes."""
    month = date.month
    seasonality = config["seasonality"]

    # Determine seasonality multiplier
    if month in seasonality["high_season_months"]:
        multiplier = seasonality["high_season_multiplier"]
    elif month in seasonality["low_season_months"]:
        multiplier = seasonality["low_season_multiplier"]
    else:
        multiplier = 1.0

    # Weekend adjustment
    if date.weekday() >= 5:  # Saturday, Sunday
        multiplier *= 1.15

    base_room_revenue = (
        config["room_count"] *
        config["average_occupancy"] *
        config["average_daily_rate"] *
        multiplier
    )

    # Add some randomness for realistic forecasting
    variance = random.uniform(0.95, 1.05)

    # Return using Planning account codes (valid PlanApp level 0 store accounts)
    return {
        "411110": round(base_room_revenue * 0.70 * variance, 2),    # Rooms Only
        "411120": round(base_room_revenue * 0.30 * variance, 2),    # Retail Web
        "421100": round(base_room_revenue * 0.15 * variance, 2),    # Breakfast Food
        "421200": round(base_room_revenue * 0.10 * variance, 2),    # Lunch Food
        "421300": round(base_room_revenue * 0.10 * variance, 2)     # Dinner Food
    }


def calculate_daily_outflows(date: datetime, config: dict) -> dict:
    """Calculate expected daily cash outflows using Planning account codes."""
    base_daily_expense = config["room_count"] * config["average_daily_rate"] * 0.6

    # Monthly payments (spread across specific days)
    day = date.day

    # Return using Planning account codes (valid PlanApp level 0 store accounts)
    outflows = {
        "611240": round(base_daily_expense * 0.05, 2) if day == 1 else 0,   # State Unemployment Insurance
        "611350": round(base_daily_expense * 0.08, 2) if day in [1, 15] else 0,  # Local Payroll Tax
        "611410": round(base_daily_expense * 0.05, 2) if day in [1, 15] else 0,  # Other Payroll Tax
        "612110": round(base_daily_expense * 0.20, 2) if day in [1, 15] else 0,  # Other Pay (main payroll)
        "612510": round(base_daily_expense * 0.02, 2) if day == 15 else 0,  # Severance Pay
        "612610": round(base_daily_expense * 0.03, 2),   # Sick Pay
        "612710": round(base_daily_expense * 0.04, 2),   # Holiday Pay
        "710100": round(base_daily_expense * 0.08, 2),   # Agency Fees
        "710110": round(base_daily_expense * 0.03, 2),   # Ambience
        "710120": round(base_daily_expense * 0.03, 2),   # Athletic Supplies
        "710130": round(base_daily_expense * 0.05, 2) if day == 1 else 0,   # Audit Charges
        "710140": round(base_daily_expense * 0.04, 2),   # Bank Charges
        "710150": round(base_daily_expense * 0.10, 2) if day in [1, 15] else 0,  # Banquet Expenses
        "710220": round(base_daily_expense * 0.06 * random.uniform(0.8, 1.2), 2),  # Cleaning Supplies
        "710310": round(base_daily_expense * 0.10, 2)    # Credit Card Commissions
    }

    return outflows


# =============================================================================
# MONTHLY AGGREGATION FOR PLANNING
# =============================================================================

def aggregate_daily_to_monthly(daily_forecasts: list[dict], config: dict) -> list[dict]:
    """
    Aggregate daily cash flow forecasts to monthly totals for Oracle Planning.

    Args:
        daily_forecasts: List of daily forecast records
        config: Hotel configuration with Planning dimensions

    Returns:
        List of monthly aggregated records ready for Planning import
    """
    monthly = {}

    for day in daily_forecasts:
        date = datetime.strptime(day["date"], "%Y-%m-%d")
        # Separate Year and Period for Planning
        year = date.strftime("FY%y")  # "FY25", "FY26"
        period = date.strftime("%b")   # "Jan", "Feb", "Mar", etc.
        key = f"{year}_{period}"       # Unique key for aggregation

        if key not in monthly:
            monthly[key] = {
                "period": period,              # "Jan", "Feb", etc.
                "year": year,                  # "FY25", "FY26"
                "month": date.month,
                "days_in_period": 0,
                "inflows": {code: 0.0 for code in INFLOW_CATEGORIES},
                "outflows": {code: 0.0 for code in OUTFLOW_CATEGORIES},
                "total_inflows": 0.0,
                "total_outflows": 0.0,
                "net_cash_flow": 0.0,
                "opening_balance": day.get("opening_balance", config["opening_cash_balance"]),
                "closing_balance": 0.0
            }

        # Sum by account code
        for code, amount in day.get("inflow_details", {}).items():
            monthly[key]["inflows"][code] += amount
        for code, amount in day.get("outflow_details", {}).items():
            monthly[key]["outflows"][code] += amount

        monthly[key]["total_inflows"] += day.get("total_inflows", 0)
        monthly[key]["total_outflows"] += day.get("total_outflows", 0)
        monthly[key]["net_cash_flow"] += day.get("net_cash_flow", 0)
        monthly[key]["closing_balance"] = day.get("closing_balance", 0)
        monthly[key]["days_in_period"] += 1

    # Round all amounts
    for period_data in monthly.values():
        period_data["total_inflows"] = round(period_data["total_inflows"], 2)
        period_data["total_outflows"] = round(period_data["total_outflows"], 2)
        period_data["net_cash_flow"] = round(period_data["net_cash_flow"], 2)
        period_data["closing_balance"] = round(period_data["closing_balance"], 2)
        for code in period_data["inflows"]:
            period_data["inflows"][code] = round(period_data["inflows"][code], 2)
        for code in period_data["outflows"]:
            period_data["outflows"][code] = round(period_data["outflows"][code], 2)

    return list(monthly.values())


def format_for_planning_import(monthly_data: list[dict], config: dict, scenario: str = "Forecast") -> list[dict]:
    """
    Format monthly aggregated data for Oracle Planning import.

    Args:
        monthly_data: Monthly aggregated records
        config: Hotel configuration with Planning dimensions
        scenario: Planning scenario (Forecast, Budget, Actual)

    Returns:
        List of records in Planning import format
    """
    planning_records = []
    dims = config.get("planning_dimensions", {})

    for month in monthly_data:
        # Create inflow records
        for account_code, amount in month["inflows"].items():
            if amount != 0:
                planning_records.append({
                    "Entity": dims.get("Entity", config.get("entity_id", "E501")),
                    "Scenario": scenario,
                    "Years": month["year"],
                    "Version": dims.get("Version", "Final"),
                    "Currency": dims.get("Currency", "USD"),
                    "Future1": dims.get("Future1", "No Future1"),
                    "CostCenter": dims.get("CostCenter", "CC1121"),
                    "Region": dims.get("Region", "R131"),
                    "Period": month["period"],
                    "Account": account_code,
                    "Amount": amount
                })

        # Create outflow records (negative for expenses)
        for account_code, amount in month["outflows"].items():
            if amount != 0:
                planning_records.append({
                    "Entity": dims.get("Entity", config.get("entity_id", "E501")),
                    "Scenario": scenario,
                    "Years": month["year"],
                    "Version": dims.get("Version", "Final"),
                    "Currency": dims.get("Currency", "USD"),
                    "Future1": dims.get("Future1", "No Future1"),
                    "CostCenter": dims.get("CostCenter", "CC1121"),
                    "Region": dims.get("Region", "R131"),
                    "Period": month["period"],
                    "Account": account_code,
                    "Amount": -amount  # Expenses as negative
                })

    return planning_records


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available cash flow forecasting tools."""
    return [
        Tool(
            name="generate_daily_forecast",
            description="Generate daily cash flow forecast for a specified date range. Returns projected inflows, outflows, and net cash position for each day.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "include_details": {
                        "type": "boolean",
                        "description": "Include detailed category breakdown",
                        "default": True
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_cash_position",
            description="Get current cash position including opening balance, today's movements, and projected closing balance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "as_of_date": {
                        "type": "string",
                        "description": "Date to check position (YYYY-MM-DD). Defaults to today."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="run_scenario",
            description="Run what-if scenario analysis on cash flow. Adjust occupancy, rates, or expenses to see impact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scenario_name": {
                        "type": "string",
                        "description": "Name for this scenario"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "occupancy_change": {
                        "type": "number",
                        "description": "Percentage change in occupancy (e.g., -10 for 10% decrease)"
                    },
                    "rate_change": {
                        "type": "number",
                        "description": "Percentage change in average daily rate"
                    },
                    "expense_change": {
                        "type": "number",
                        "description": "Percentage change in operating expenses"
                    }
                },
                "required": ["scenario_name", "start_date", "end_date"]
            }
        ),
        Tool(
            name="validate_forecast",
            description="Validate forecast accuracy against actual cash flow data. Calculate variance and accuracy metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "forecast_date": {
                        "type": "string",
                        "description": "Date of forecast to validate (YYYY-MM-DD)"
                    },
                    "actual_inflows": {
                        "type": "number",
                        "description": "Actual total inflows for the date"
                    },
                    "actual_outflows": {
                        "type": "number",
                        "description": "Actual total outflows for the date"
                    }
                },
                "required": ["forecast_date", "actual_inflows", "actual_outflows"]
            }
        ),
        Tool(
            name="export_report",
            description="Export cash flow forecast report in various formats (JSON, CSV, summary).",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "csv", "summary"],
                        "description": "Export format",
                        "default": "summary"
                    },
                    "include_scenarios": {
                        "type": "boolean",
                        "description": "Include saved scenarios in report",
                        "default": False
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="optimize_pricing",
            description="Calculate optimal room rates using dynamic pricing. Considers occupancy, day of week, seasonality, lead time, local events, and competitor rates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "current_occupancy": {
                        "type": "number",
                        "description": "Current occupancy percentage (0-100). If not provided, uses hotel average."
                    },
                    "lead_days": {
                        "type": "integer",
                        "description": "Days until guest arrival (0 = same day booking). Affects pricing."
                    },
                    "include_breakdown": {
                        "type": "boolean",
                        "description": "Include detailed breakdown of pricing factors",
                        "default": True
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_events",
            description="Get local events calendar that impact hotel demand and pricing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "event_type": {
                        "type": "string",
                        "enum": ["all", "convention", "sports", "festival", "holiday", "shopping"],
                        "description": "Filter by event type",
                        "default": "all"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_competitor_rates",
            description="Get competitor hotel rates for market comparison and positioning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to check competitor rates (YYYY-MM-DD)"
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="sync_rates_to_opera",
            description="Sync optimized dynamic pricing rates to Oracle Opera PMS. Pushes recommended rates for the specified period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "rate_code": {
                        "type": "string",
                        "description": "Opera rate code to update (default: BAR)",
                        "default": "BAR"
                    },
                    "room_type": {
                        "type": "string",
                        "description": "Room type code (default: STD)",
                        "default": "STD"
                    },
                    "preview_only": {
                        "type": "boolean",
                        "description": "If true, shows rates without syncing to Opera",
                        "default": False
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="fetch_opera_rates",
            description="Fetch current rates from Oracle Opera PMS for comparison with dynamic pricing recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "rate_code": {
                        "type": "string",
                        "description": "Opera rate code to fetch (default: BAR)",
                        "default": "BAR"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_opera_inventory",
            description="Get room inventory and occupancy data from Oracle Opera PMS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        # Oracle Planning Integration Tools
        Tool(
            name="export_monthly_for_planning",
            description="Generate monthly aggregated cash flow forecast for Oracle Planning import. Rolls up daily forecasts to monthly periods with Planning dimension alignment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "scenario": {
                        "type": "string",
                        "description": "Planning scenario (Forecast, Budget, Actual)",
                        "default": "Forecast"
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: json, csv, or summary",
                        "default": "csv"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="sync_to_planning",
            description="Push monthly cash flow forecast to Oracle Planning Cloud (PlanApp). Generates daily forecasts, aggregates to monthly periods, and loads to Planning. Typically used for 3-month rolling forecast.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Forecast start date in YYYY-MM-DD format (e.g., 2025-01-01 for Jan)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Forecast end date in YYYY-MM-DD format (e.g., 2025-03-31 for 3 months)"
                    },
                    "scenario": {
                        "type": "string",
                        "description": "Planning scenario to load data into (Forecast, Budget)",
                        "default": "Forecast"
                    },
                    "load_method": {
                        "type": "string",
                        "description": "Data load method: REPLACE (overwrite) or ACCUMULATE (add)",
                        "default": "REPLACE"
                    },
                    "preview_only": {
                        "type": "boolean",
                        "description": "If true, shows data without syncing to Planning",
                        "default": False
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_planning_actuals",
            description="Fetch last month's actuals from Oracle Planning to baseline forecast data. Used for calibrating forecast accuracy.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Period to fetch (e.g., Dec-24, Jan-25)"
                    },
                    "entity": {
                        "type": "string",
                        "description": "Entity/Hotel code (default: from config)",
                        "default": "E501"
                    }
                },
                "required": ["period"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute cash flow forecasting tools."""

    config = load_hotel_data()

    if name == "generate_daily_forecast":
        return await generate_daily_forecast(arguments, config)
    elif name == "get_cash_position":
        return await get_cash_position(arguments, config)
    elif name == "run_scenario":
        return await run_scenario(arguments, config)
    elif name == "validate_forecast":
        return await validate_forecast(arguments, config)
    elif name == "export_report":
        return await export_report(arguments, config)
    elif name == "optimize_pricing":
        return await optimize_pricing(arguments, config)
    elif name == "get_events":
        return await get_events_calendar(arguments, config)
    elif name == "get_competitor_rates":
        return await get_competitor_analysis(arguments, config)
    elif name == "sync_rates_to_opera":
        return await sync_rates_to_opera(arguments, config)
    elif name == "fetch_opera_rates":
        return await fetch_opera_rates(arguments, config)
    elif name == "get_opera_inventory":
        return await get_opera_inventory(arguments, config)
    # Oracle Planning Integration
    elif name == "export_monthly_for_planning":
        return await export_monthly_for_planning(arguments, config)
    elif name == "sync_to_planning":
        return await sync_to_planning(arguments, config)
    elif name == "get_planning_actuals":
        return await get_planning_actuals(arguments, config)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def generate_daily_forecast(args: dict, config: dict) -> list[TextContent]:
    """Generate daily cash flow forecast."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        include_details = args.get("include_details", True)

        if end_date < start_date:
            return [TextContent(type="text", text="Error: End date must be after start date")]

        if (end_date - start_date).days > 90:
            return [TextContent(type="text", text="Error: Maximum forecast period is 90 days")]

        forecast = []
        running_balance = config["opening_cash_balance"]

        current_date = start_date
        while current_date <= end_date:
            inflows = calculate_daily_inflows(current_date, config)
            outflows = calculate_daily_outflows(current_date, config)

            total_inflows = sum(inflows.values())
            total_outflows = sum(outflows.values())
            net_cash_flow = total_inflows - total_outflows
            running_balance += net_cash_flow

            day_forecast = {
                "date": current_date.strftime("%Y-%m-%d"),
                "day_of_week": current_date.strftime("%A"),
                "total_inflows": round(total_inflows, 2),
                "total_outflows": round(total_outflows, 2),
                "net_cash_flow": round(net_cash_flow, 2),
                "closing_balance": round(running_balance, 2),
                "below_minimum": running_balance < config["minimum_cash_reserve"]
            }

            if include_details:
                day_forecast["inflow_details"] = inflows
                day_forecast["outflow_details"] = outflows

            forecast.append(day_forecast)
            current_date += timedelta(days=1)

        # Summary statistics
        total_period_inflows = sum(d["total_inflows"] for d in forecast)
        total_period_outflows = sum(d["total_outflows"] for d in forecast)

        result = {
            "hotel_name": config["hotel_name"],
            "forecast_period": {
                "start": args["start_date"],
                "end": args["end_date"],
                "days": len(forecast)
            },
            "summary": {
                "opening_balance": config["opening_cash_balance"],
                "total_inflows": round(total_period_inflows, 2),
                "total_outflows": round(total_period_outflows, 2),
                "net_change": round(total_period_inflows - total_period_outflows, 2),
                "closing_balance": round(running_balance, 2),
                "days_below_minimum": sum(1 for d in forecast if d["below_minimum"])
            },
            "daily_forecast": forecast
        }

        # Save forecast for later validation
        forecast_file = DATA_DIR / f"forecast_{args['start_date']}_{args['end_date']}.json"
        with open(forecast_file, "w") as f:
            json.dump(result, f, indent=2)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        return [TextContent(type="text", text=f"Error generating forecast: {str(e)}")]


async def get_cash_position(args: dict, config: dict) -> list[TextContent]:
    """Get current cash position."""
    try:
        if args.get("as_of_date"):
            check_date = datetime.strptime(args["as_of_date"], "%Y-%m-%d")
        else:
            check_date = datetime.now()

        inflows = calculate_daily_inflows(check_date, config)
        outflows = calculate_daily_outflows(check_date, config)

        total_inflows = sum(inflows.values())
        total_outflows = sum(outflows.values())
        net_movement = total_inflows - total_outflows

        # Load any saved actuals
        actuals_file = DATA_DIR / f"actuals_{check_date.strftime('%Y-%m-%d')}.json"
        has_actuals = actuals_file.exists()

        position = {
            "hotel_name": config["hotel_name"],
            "as_of_date": check_date.strftime("%Y-%m-%d"),
            "day_of_week": check_date.strftime("%A"),
            "cash_position": {
                "opening_balance": config["opening_cash_balance"],
                "projected_inflows": round(total_inflows, 2),
                "projected_outflows": round(total_outflows, 2),
                "net_movement": round(net_movement, 2),
                "projected_closing": round(config["opening_cash_balance"] + net_movement, 2)
            },
            "thresholds": {
                "minimum_reserve": config["minimum_cash_reserve"],
                "status": "OK" if (config["opening_cash_balance"] + net_movement) >= config["minimum_cash_reserve"] else "BELOW MINIMUM"
            },
            "inflow_breakdown": inflows,
            "outflow_breakdown": outflows,
            "has_actual_data": has_actuals
        }

        return [TextContent(type="text", text=json.dumps(position, indent=2))]

    except Exception as e:
        logger.error(f"Error getting cash position: {e}")
        return [TextContent(type="text", text=f"Error getting cash position: {str(e)}")]


async def run_scenario(args: dict, config: dict) -> list[TextContent]:
    """Run what-if scenario analysis."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")

        # Apply scenario adjustments
        scenario_config = config.copy()

        occupancy_change = args.get("occupancy_change", 0) / 100
        rate_change = args.get("rate_change", 0) / 100
        expense_change = args.get("expense_change", 0) / 100

        scenario_config["average_occupancy"] = config["average_occupancy"] * (1 + occupancy_change)
        scenario_config["average_daily_rate"] = config["average_daily_rate"] * (1 + rate_change)

        # Generate baseline forecast
        baseline_balance = config["opening_cash_balance"]
        scenario_balance = config["opening_cash_balance"]

        baseline_data = []
        scenario_data = []

        current_date = start_date
        while current_date <= end_date:
            # Baseline
            base_inflows = calculate_daily_inflows(current_date, config)
            base_outflows = calculate_daily_outflows(current_date, config)
            base_net = sum(base_inflows.values()) - sum(base_outflows.values())
            baseline_balance += base_net
            baseline_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "net_cash_flow": round(base_net, 2),
                "closing_balance": round(baseline_balance, 2)
            })

            # Scenario
            scen_inflows = calculate_daily_inflows(current_date, scenario_config)
            scen_outflows = calculate_daily_outflows(current_date, config)  # Base outflows

            # Apply expense change
            adjusted_outflows = {k: v * (1 + expense_change) for k, v in scen_outflows.items()}

            scen_net = sum(scen_inflows.values()) - sum(adjusted_outflows.values())
            scenario_balance += scen_net
            scenario_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "net_cash_flow": round(scen_net, 2),
                "closing_balance": round(scenario_balance, 2)
            })

            current_date += timedelta(days=1)

        result = {
            "scenario_name": args["scenario_name"],
            "period": {
                "start": args["start_date"],
                "end": args["end_date"],
                "days": len(baseline_data)
            },
            "adjustments": {
                "occupancy_change": f"{args.get('occupancy_change', 0)}%",
                "rate_change": f"{args.get('rate_change', 0)}%",
                "expense_change": f"{args.get('expense_change', 0)}%"
            },
            "comparison": {
                "baseline": {
                    "total_net_cash_flow": round(sum(d["net_cash_flow"] for d in baseline_data), 2),
                    "final_balance": round(baseline_balance, 2),
                    "days_below_minimum": sum(1 for d in baseline_data if d["closing_balance"] < config["minimum_cash_reserve"])
                },
                "scenario": {
                    "total_net_cash_flow": round(sum(d["net_cash_flow"] for d in scenario_data), 2),
                    "final_balance": round(scenario_balance, 2),
                    "days_below_minimum": sum(1 for d in scenario_data if d["closing_balance"] < config["minimum_cash_reserve"])
                },
                "impact": {
                    "cash_flow_difference": round(
                        sum(d["net_cash_flow"] for d in scenario_data) -
                        sum(d["net_cash_flow"] for d in baseline_data), 2
                    ),
                    "final_balance_difference": round(scenario_balance - baseline_balance, 2)
                }
            },
            "daily_comparison": [
                {
                    "date": baseline_data[i]["date"],
                    "baseline_balance": baseline_data[i]["closing_balance"],
                    "scenario_balance": scenario_data[i]["closing_balance"],
                    "difference": round(scenario_data[i]["closing_balance"] - baseline_data[i]["closing_balance"], 2)
                }
                for i in range(len(baseline_data))
            ]
        }

        # Save scenario
        scenario_file = DATA_DIR / f"scenario_{args['scenario_name'].replace(' ', '_')}.json"
        with open(scenario_file, "w") as f:
            json.dump(result, f, indent=2)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error running scenario: {e}")
        return [TextContent(type="text", text=f"Error running scenario: {str(e)}")]


async def validate_forecast(args: dict, config: dict) -> list[TextContent]:
    """Validate forecast against actuals."""
    try:
        forecast_date = datetime.strptime(args["forecast_date"], "%Y-%m-%d")
        actual_inflows = args["actual_inflows"]
        actual_outflows = args["actual_outflows"]

        # Get forecasted values
        forecasted_inflows = calculate_daily_inflows(forecast_date, config)
        forecasted_outflows = calculate_daily_outflows(forecast_date, config)

        total_forecasted_inflows = sum(forecasted_inflows.values())
        total_forecasted_outflows = sum(forecasted_outflows.values())

        # Calculate variances
        inflow_variance = actual_inflows - total_forecasted_inflows
        outflow_variance = actual_outflows - total_forecasted_outflows

        inflow_variance_pct = (inflow_variance / total_forecasted_inflows * 100) if total_forecasted_inflows else 0
        outflow_variance_pct = (outflow_variance / total_forecasted_outflows * 100) if total_forecasted_outflows else 0

        # Calculate accuracy (100% - absolute variance percentage)
        inflow_accuracy = max(0, 100 - abs(inflow_variance_pct))
        outflow_accuracy = max(0, 100 - abs(outflow_variance_pct))

        validation = {
            "date": args["forecast_date"],
            "forecast": {
                "total_inflows": round(total_forecasted_inflows, 2),
                "total_outflows": round(total_forecasted_outflows, 2),
                "net_cash_flow": round(total_forecasted_inflows - total_forecasted_outflows, 2)
            },
            "actuals": {
                "total_inflows": actual_inflows,
                "total_outflows": actual_outflows,
                "net_cash_flow": round(actual_inflows - actual_outflows, 2)
            },
            "variance": {
                "inflows": {
                    "amount": round(inflow_variance, 2),
                    "percentage": round(inflow_variance_pct, 2),
                    "direction": "favorable" if inflow_variance > 0 else "unfavorable"
                },
                "outflows": {
                    "amount": round(outflow_variance, 2),
                    "percentage": round(outflow_variance_pct, 2),
                    "direction": "unfavorable" if outflow_variance > 0 else "favorable"
                },
                "net_impact": round((actual_inflows - actual_outflows) - (total_forecasted_inflows - total_forecasted_outflows), 2)
            },
            "accuracy": {
                "inflow_accuracy": round(inflow_accuracy, 2),
                "outflow_accuracy": round(outflow_accuracy, 2),
                "overall_accuracy": round((inflow_accuracy + outflow_accuracy) / 2, 2)
            },
            "assessment": "ACCEPTABLE" if (inflow_accuracy + outflow_accuracy) / 2 >= 85 else "NEEDS REVIEW"
        }

        # Save actuals for future reference
        actuals_file = DATA_DIR / f"actuals_{args['forecast_date']}.json"
        with open(actuals_file, "w") as f:
            json.dump({
                "date": args["forecast_date"],
                "actual_inflows": actual_inflows,
                "actual_outflows": actual_outflows,
                "validation": validation
            }, f, indent=2)

        return [TextContent(type="text", text=json.dumps(validation, indent=2))]

    except Exception as e:
        logger.error(f"Error validating forecast: {e}")
        return [TextContent(type="text", text=f"Error validating forecast: {str(e)}")]


async def export_report(args: dict, config: dict) -> list[TextContent]:
    """Export cash flow report."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        export_format = args.get("format", "summary")
        include_scenarios = args.get("include_scenarios", False)

        # Generate forecast data
        forecast_data = []
        running_balance = config["opening_cash_balance"]

        current_date = start_date
        while current_date <= end_date:
            inflows = calculate_daily_inflows(current_date, config)
            outflows = calculate_daily_outflows(current_date, config)

            total_in = sum(inflows.values())
            total_out = sum(outflows.values())
            running_balance += (total_in - total_out)

            forecast_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "inflows": round(total_in, 2),
                "outflows": round(total_out, 2),
                "net": round(total_in - total_out, 2),
                "balance": round(running_balance, 2),
                "inflow_details": inflows,
                "outflow_details": outflows
            })

            current_date += timedelta(days=1)

        if export_format == "json":
            report = {
                "report_type": "Daily Cash Flow Forecast",
                "hotel_name": config["hotel_name"],
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start": args["start_date"],
                    "end": args["end_date"]
                },
                "opening_balance": config["opening_cash_balance"],
                "data": forecast_data
            }

            output_file = DATA_DIR / f"report_{args['start_date']}_{args['end_date']}.json"
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)

            return [TextContent(type="text", text=f"JSON report exported to: {output_file}\n\n{json.dumps(report, indent=2)}")]

        elif export_format == "csv":
            csv_lines = ["Date,Day,Inflows,Outflows,Net Cash Flow,Closing Balance"]
            for d in forecast_data:
                date_obj = datetime.strptime(d["date"], "%Y-%m-%d")
                csv_lines.append(f"{d['date']},{date_obj.strftime('%A')},{d['inflows']},{d['outflows']},{d['net']},{d['balance']}")

            csv_content = "\n".join(csv_lines)
            output_file = DATA_DIR / f"report_{args['start_date']}_{args['end_date']}.csv"
            with open(output_file, "w") as f:
                f.write(csv_content)

            return [TextContent(type="text", text=f"CSV report exported to: {output_file}\n\n{csv_content}")]

        else:  # summary
            total_inflows = sum(d["inflows"] for d in forecast_data)
            total_outflows = sum(d["outflows"] for d in forecast_data)

            summary = f"""
╔══════════════════════════════════════════════════════════════════╗
║           CASH FLOW FORECAST SUMMARY REPORT                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Hotel: {config['hotel_name']:<54} ║
║  Period: {args['start_date']} to {args['end_date']:<36} ║
║  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M'):<50} ║
╠══════════════════════════════════════════════════════════════════╣
║  CASH POSITION                                                   ║
║  ─────────────────────────────────────────────────────────────── ║
║  Opening Balance:     ${config['opening_cash_balance']:>15,.2f}                      ║
║  Total Inflows:       ${total_inflows:>15,.2f}                      ║
║  Total Outflows:      ${total_outflows:>15,.2f}                      ║
║  Net Change:          ${(total_inflows - total_outflows):>15,.2f}                      ║
║  Closing Balance:     ${running_balance:>15,.2f}                      ║
╠══════════════════════════════════════════════════════════════════╣
║  DAILY AVERAGES                                                  ║
║  ─────────────────────────────────────────────────────────────── ║
║  Avg Daily Inflows:   ${(total_inflows/len(forecast_data)):>15,.2f}                      ║
║  Avg Daily Outflows:  ${(total_outflows/len(forecast_data)):>15,.2f}                      ║
║  Avg Daily Net:       ${((total_inflows-total_outflows)/len(forecast_data)):>15,.2f}                      ║
╠══════════════════════════════════════════════════════════════════╣
║  RISK INDICATORS                                                 ║
║  ─────────────────────────────────────────────────────────────── ║
║  Minimum Reserve:     ${config['minimum_cash_reserve']:>15,.2f}                      ║
║  Days Below Minimum:  {sum(1 for d in forecast_data if d['balance'] < config['minimum_cash_reserve']):>15}                      ║
║  Status: {'HEALTHY' if running_balance >= config['minimum_cash_reserve'] else 'ATTENTION REQUIRED':<55} ║
╚══════════════════════════════════════════════════════════════════╝
"""
            return [TextContent(type="text", text=summary)]

    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return [TextContent(type="text", text=f"Error exporting report: {str(e)}")]


async def optimize_pricing(args: dict, config: dict) -> list[TextContent]:
    """Calculate optimal room rates using dynamic pricing."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        current_occupancy = args.get("current_occupancy")
        if current_occupancy:
            current_occupancy = current_occupancy / 100  # Convert to decimal
        lead_days = args.get("lead_days", 0)
        include_breakdown = args.get("include_breakdown", True)

        if end_date < start_date:
            return [TextContent(type="text", text="Error: End date must be after start date")]

        if (end_date - start_date).days > 90:
            return [TextContent(type="text", text="Error: Maximum period is 90 days")]

        pricing_recommendations = []
        total_base_revenue = 0
        total_optimized_revenue = 0

        current_date = start_date
        while current_date <= end_date:
            rate_info = calculate_dynamic_rate(
                current_date, config,
                current_occupancy=current_occupancy,
                lead_days=lead_days,
                include_breakdown=include_breakdown
            )

            # Calculate revenue impact
            rooms_sold = config["room_count"] * (current_occupancy or config["average_occupancy"])
            base_revenue = rooms_sold * config["average_daily_rate"]
            optimized_revenue = rooms_sold * rate_info["optimized_rate"]

            total_base_revenue += base_revenue
            total_optimized_revenue += optimized_revenue

            rate_info["projected_rooms"] = round(rooms_sold)
            rate_info["base_revenue"] = round(base_revenue, 2)
            rate_info["optimized_revenue"] = round(optimized_revenue, 2)
            rate_info["revenue_uplift"] = round(optimized_revenue - base_revenue, 2)

            pricing_recommendations.append(rate_info)
            current_date += timedelta(days=1)

        result = {
            "hotel_name": config["hotel_name"],
            "period": {
                "start": args["start_date"],
                "end": args["end_date"],
                "days": len(pricing_recommendations)
            },
            "pricing_parameters": {
                "base_rate": config["average_daily_rate"],
                "min_rate": DYNAMIC_PRICING_CONFIG["min_rate"],
                "max_rate": DYNAMIC_PRICING_CONFIG["max_rate"],
                "occupancy_used": round((current_occupancy or config["average_occupancy"]) * 100, 1),
                "lead_days": lead_days
            },
            "summary": {
                "avg_base_rate": config["average_daily_rate"],
                "avg_optimized_rate": round(sum(r["optimized_rate"] for r in pricing_recommendations) / len(pricing_recommendations), 2),
                "total_base_revenue": round(total_base_revenue, 2),
                "total_optimized_revenue": round(total_optimized_revenue, 2),
                "total_revenue_uplift": round(total_optimized_revenue - total_base_revenue, 2),
                "uplift_percentage": round((total_optimized_revenue - total_base_revenue) / total_base_revenue * 100, 1) if total_base_revenue > 0 else 0
            },
            "daily_recommendations": pricing_recommendations
        }

        # Save recommendations
        output_file = DATA_DIR / f"pricing_{args['start_date']}_{args['end_date']}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error optimizing pricing: {e}")
        return [TextContent(type="text", text=f"Error optimizing pricing: {str(e)}")]


async def get_events_calendar(args: dict, config: dict) -> list[TextContent]:
    """Get local events calendar."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        event_type = args.get("event_type", "all")

        events = []
        current_date = start_date
        while current_date <= end_date:
            event = get_event_impact(current_date)
            if event:
                if event_type == "all" or event["type"] == event_type:
                    events.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "day_of_week": current_date.strftime("%A"),
                        "name": event["name"],
                        "type": event["type"],
                        "demand_impact": f"+{int(event['impact'] * 100)}%",
                        "recommended_rate_adjustment": f"+{int(event['impact'] * 100)}%"
                    })
            current_date += timedelta(days=1)

        result = {
            "hotel_name": config["hotel_name"],
            "location": "Chicago, Illinois",
            "period": {
                "start": args["start_date"],
                "end": args["end_date"]
            },
            "filter": event_type,
            "total_events": len(events),
            "events": events,
            "event_type_summary": {}
        }

        # Summarize by type
        for event in events:
            etype = event["type"]
            if etype not in result["event_type_summary"]:
                result["event_type_summary"][etype] = 0
            result["event_type_summary"][etype] += 1

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return [TextContent(type="text", text=f"Error getting events: {str(e)}")]


async def get_competitor_analysis(args: dict, config: dict) -> list[TextContent]:
    """Get competitor rate analysis."""
    try:
        check_date = datetime.strptime(args["date"], "%Y-%m-%d")

        # Get competitor rates
        competitor_rates = get_competitor_rates(check_date)

        # Get our dynamic rate
        our_rate = calculate_dynamic_rate(check_date, config, include_breakdown=True)

        # Calculate market position
        avg_competitor = sum(competitor_rates.values()) / len(competitor_rates)
        min_competitor = min(competitor_rates.values())
        max_competitor = max(competitor_rates.values())

        result = {
            "hotel_name": config["hotel_name"],
            "date": args["date"],
            "day_of_week": check_date.strftime("%A"),
            "our_pricing": {
                "base_rate": config["average_daily_rate"],
                "optimized_rate": our_rate["optimized_rate"],
                "adjustment": our_rate["total_adjustment_pct"]
            },
            "competitor_rates": competitor_rates,
            "market_analysis": {
                "average": round(avg_competitor, 2),
                "minimum": round(min_competitor, 2),
                "maximum": round(max_competitor, 2),
                "spread": round(max_competitor - min_competitor, 2)
            },
            "our_position": {
                "vs_average": round(our_rate["optimized_rate"] - avg_competitor, 2),
                "vs_average_pct": round((our_rate["optimized_rate"] - avg_competitor) / avg_competitor * 100, 1),
                "rank": sorted(list(competitor_rates.values()) + [our_rate["optimized_rate"]], reverse=True).index(our_rate["optimized_rate"]) + 1,
                "positioning": "premium" if our_rate["optimized_rate"] > avg_competitor else "value" if our_rate["optimized_rate"] < avg_competitor else "market"
            },
            "recommendations": []
        }

        # Add recommendations
        if our_rate["optimized_rate"] > max_competitor * 1.1:
            result["recommendations"].append("Rate significantly above market - consider reducing to maintain competitiveness")
        elif our_rate["optimized_rate"] < min_competitor * 0.9:
            result["recommendations"].append("Rate below market floor - opportunity to increase rates")
        else:
            result["recommendations"].append("Rate well-positioned within market range")

        event = get_event_impact(check_date)
        if event:
            result["event_impact"] = {
                "name": event["name"],
                "type": event["type"],
                "adjustment": f"+{int(event['impact'] * 100)}%"
            }
            result["recommendations"].append(f"Event '{event['name']}' - ensure rate captures demand surge")

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting competitor rates: {e}")
        return [TextContent(type="text", text=f"Error getting competitor rates: {str(e)}")]


async def sync_rates_to_opera(args: dict, config: dict) -> list[TextContent]:
    """Sync dynamic pricing rates to Oracle Opera PMS."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        rate_code = args.get("rate_code", "BAR")
        room_type = args.get("room_type", "STD")
        preview_only = args.get("preview_only", False)

        if end_date < start_date:
            return [TextContent(type="text", text="Error: End date must be after start date")]

        if (end_date - start_date).days > 90:
            return [TextContent(type="text", text="Error: Maximum period is 90 days")]

        # Get Opera client
        opera = get_opera_client(config)

        # Calculate optimized rates
        rates_to_sync = []
        current_date = start_date
        while current_date <= end_date:
            rate_info = calculate_dynamic_rate(current_date, config, include_breakdown=False)
            rates_to_sync.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "rate_code": rate_code,
                "room_type": room_type,
                "amount": rate_info["optimized_rate"],
                "day_of_week": rate_info["day_of_week"],
                "adjustment_pct": rate_info["total_adjustment_pct"]
            })
            current_date += timedelta(days=1)

        result = {
            "hotel_name": config["hotel_name"],
            "opera_hotel_id": config.get("opera_hotel_id", "CHICAGOL7"),
            "period": {
                "start": args["start_date"],
                "end": args["end_date"],
                "days": len(rates_to_sync)
            },
            "rate_code": rate_code,
            "room_type": room_type,
            "preview_only": preview_only,
            "rates": rates_to_sync
        }

        if preview_only:
            result["status"] = "PREVIEW - rates not synced to Opera"
            result["summary"] = {
                "avg_rate": round(sum(r["amount"] for r in rates_to_sync) / len(rates_to_sync), 2),
                "min_rate": min(r["amount"] for r in rates_to_sync),
                "max_rate": max(r["amount"] for r in rates_to_sync)
            }
        else:
            # Sync to Opera
            sync_result = opera.bulk_update_rates(rates_to_sync)
            result["sync_result"] = sync_result
            result["status"] = f"SYNCED - {sync_result['success']}/{sync_result['total']} rates updated in Opera"

        # Save sync log
        log_file = DATA_DIR / f"opera_sync_{args['start_date']}_{args['end_date']}.json"
        with open(log_file, "w") as f:
            json.dump(result, f, indent=2)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error syncing rates to Opera: {e}")
        return [TextContent(type="text", text=f"Error syncing rates to Opera: {str(e)}")]


async def fetch_opera_rates(args: dict, config: dict) -> list[TextContent]:
    """Fetch current rates from Oracle Opera PMS."""
    try:
        start_date = args["start_date"]
        end_date = args["end_date"]
        rate_code = args.get("rate_code", "BAR")

        # Get Opera client
        opera = get_opera_client(config)

        # Fetch current rates
        opera_rates = opera.get_current_rates(start_date, end_date, rate_code)

        # Get our dynamic pricing recommendations for comparison
        comparison = []
        for opera_rate in opera_rates:
            date = datetime.strptime(opera_rate["date"], "%Y-%m-%d")
            dynamic = calculate_dynamic_rate(date, config, include_breakdown=False)

            comparison.append({
                "date": opera_rate["date"],
                "day_of_week": dynamic["day_of_week"],
                "opera_rate": opera_rate["amount"],
                "recommended_rate": dynamic["optimized_rate"],
                "difference": round(dynamic["optimized_rate"] - opera_rate["amount"], 2),
                "difference_pct": round((dynamic["optimized_rate"] - opera_rate["amount"]) / opera_rate["amount"] * 100, 1) if opera_rate["amount"] > 0 else 0,
                "action": "INCREASE" if dynamic["optimized_rate"] > opera_rate["amount"] * 1.02 else "DECREASE" if dynamic["optimized_rate"] < opera_rate["amount"] * 0.98 else "OK"
            })

        # Summary
        rates_to_increase = sum(1 for c in comparison if c["action"] == "INCREASE")
        rates_to_decrease = sum(1 for c in comparison if c["action"] == "DECREASE")
        potential_uplift = sum(c["difference"] for c in comparison if c["difference"] > 0)

        result = {
            "hotel_name": config["hotel_name"],
            "opera_hotel_id": config.get("opera_hotel_id", "CHICAGOL7"),
            "period": {
                "start": start_date,
                "end": end_date,
                "days": len(comparison)
            },
            "rate_code": rate_code,
            "summary": {
                "rates_to_increase": rates_to_increase,
                "rates_to_decrease": rates_to_decrease,
                "rates_ok": len(comparison) - rates_to_increase - rates_to_decrease,
                "avg_opera_rate": round(sum(c["opera_rate"] for c in comparison) / len(comparison), 2),
                "avg_recommended_rate": round(sum(c["recommended_rate"] for c in comparison) / len(comparison), 2),
                "potential_daily_uplift": round(potential_uplift / len(comparison), 2) if comparison else 0
            },
            "comparison": comparison
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error fetching Opera rates: {e}")
        return [TextContent(type="text", text=f"Error fetching Opera rates: {str(e)}")]


async def get_opera_inventory(args: dict, config: dict) -> list[TextContent]:
    """Get room inventory from Oracle Opera PMS."""
    try:
        start_date = args["start_date"]
        end_date = args["end_date"]

        # Get Opera client
        opera = get_opera_client(config)

        # Fetch inventory
        inventory = opera.get_inventory(start_date, end_date)

        # Enhance with pricing recommendations based on occupancy
        enhanced_inventory = []
        for inv in inventory:
            occupancy = inv.get("occupancy", 75) / 100
            date = datetime.strptime(inv["date"], "%Y-%m-%d")

            # Get dynamic rate based on actual occupancy
            dynamic = calculate_dynamic_rate(date, config, current_occupancy=occupancy, include_breakdown=False)

            enhanced_inventory.append({
                "date": inv["date"],
                "day_of_week": date.strftime("%A"),
                "total_rooms": inv["totalRooms"],
                "available": inv["available"],
                "occupied": inv["occupied"],
                "occupancy_pct": inv["occupancy"],
                "occupancy_tier": "sold_out" if occupancy > 0.95 else "very_high" if occupancy > 0.85 else "high" if occupancy > 0.70 else "moderate" if occupancy > 0.50 else "low",
                "recommended_rate": dynamic["optimized_rate"],
                "rate_adjustment": f"{dynamic['total_adjustment_pct']:+.1f}%"
            })

        # Summary
        avg_occupancy = sum(i["occupancy_pct"] for i in enhanced_inventory) / len(enhanced_inventory) if enhanced_inventory else 0
        total_room_nights = sum(i["total_rooms"] for i in enhanced_inventory)
        total_available = sum(i["available"] for i in enhanced_inventory)

        result = {
            "hotel_name": config["hotel_name"],
            "opera_hotel_id": config.get("opera_hotel_id", "CHICAGOL7"),
            "period": {
                "start": start_date,
                "end": end_date,
                "days": len(enhanced_inventory)
            },
            "summary": {
                "total_room_nights": total_room_nights,
                "total_available": total_available,
                "total_occupied": total_room_nights - total_available,
                "avg_occupancy": round(avg_occupancy, 1),
                "high_demand_days": sum(1 for i in enhanced_inventory if i["occupancy_pct"] > 85),
                "low_demand_days": sum(1 for i in enhanced_inventory if i["occupancy_pct"] < 50)
            },
            "daily_inventory": enhanced_inventory
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting Opera inventory: {e}")
        return [TextContent(type="text", text=f"Error getting Opera inventory: {str(e)}")]


# =============================================================================
# ORACLE PLANNING INTEGRATION TOOLS
# =============================================================================

async def export_monthly_for_planning(args: dict, config: dict) -> list[TextContent]:
    """Generate monthly aggregated forecast for Oracle Planning import."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        scenario = args.get("scenario", "Forecast")
        output_format = args.get("format", "csv")

        if end_date < start_date:
            return [TextContent(type="text", text="Error: End date must be after start date")]

        # Generate daily forecasts first
        forecast = []
        running_balance = config["opening_cash_balance"]
        current_date = start_date

        while current_date <= end_date:
            inflows = calculate_daily_inflows(current_date, config)
            outflows = calculate_daily_outflows(current_date, config)

            total_inflows = sum(inflows.values())
            total_outflows = sum(outflows.values())
            net_cash_flow = total_inflows - total_outflows
            running_balance += net_cash_flow

            forecast.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "opening_balance": running_balance - net_cash_flow,
                "inflow_details": inflows,
                "outflow_details": outflows,
                "total_inflows": total_inflows,
                "total_outflows": total_outflows,
                "net_cash_flow": net_cash_flow,
                "closing_balance": running_balance
            })

            current_date += timedelta(days=1)

        # Aggregate to monthly
        monthly_data = aggregate_daily_to_monthly(forecast, config)

        # Format for Planning import
        planning_records = format_for_planning_import(monthly_data, config, scenario)

        # Generate output based on format
        if output_format == "csv":
            # Generate CSV with PlanApp dimension order
            csv_lines = ["Entity,Scenario,Years,Version,Currency,Future1,CostCenter,Region,Period,Account,Amount"]
            for record in planning_records:
                csv_lines.append(
                    f"{record['Entity']},{record['Scenario']},{record['Years']},"
                    f"{record['Version']},{record['Currency']},{record['Future1']},"
                    f"{record['CostCenter']},{record['Region']},{record['Period']},"
                    f"{record['Account']},{record['Amount']}"
                )
            output = "\n".join(csv_lines)

            # Save to file
            filename = f"planning_export_{args['start_date']}_{args['end_date']}.csv"
            filepath = DATA_DIR / filename
            with open(filepath, "w") as f:
                f.write(output)

            result = {
                "status": "success",
                "message": f"Monthly forecast exported for Planning",
                "file": str(filepath),
                "scenario": scenario,
                "periods": [f"{m['year']}:{m['period']}" for m in monthly_data],
                "records_generated": len(planning_records),
                "preview": "\n".join(csv_lines[:10]) + "\n..." if len(csv_lines) > 10 else output
            }

        elif output_format == "summary":
            # Generate summary report
            summary_lines = [
                "=" * 60,
                f"MONTHLY FORECAST FOR ORACLE PLANNING",
                f"Scenario: {scenario}",
                f"Period: {args['start_date']} to {args['end_date']}",
                "=" * 60,
                ""
            ]

            for month in monthly_data:
                summary_lines.extend([
                    f"\n{month['year']} - {month['period']} ({month['days_in_period']} days)",
                    "-" * 40,
                    f"  Total Inflows:  ${month['total_inflows']:>12,.2f}",
                    f"  Total Outflows: ${month['total_outflows']:>12,.2f}",
                    f"  Net Cash Flow:  ${month['net_cash_flow']:>12,.2f}",
                    f"  Closing Balance: ${month['closing_balance']:>11,.2f}"
                ])

            output = "\n".join(summary_lines)
            result = {
                "status": "success",
                "scenario": scenario,
                "summary": output,
                "monthly_totals": monthly_data
            }

        else:  # json
            # Save JSON
            filename = f"planning_export_{args['start_date']}_{args['end_date']}.json"
            filepath = DATA_DIR / filename
            with open(filepath, "w") as f:
                json.dump(planning_records, f, indent=2)

            result = {
                "status": "success",
                "message": f"Monthly forecast exported for Planning",
                "file": str(filepath),
                "scenario": scenario,
                "periods": [f"{m['year']}:{m['period']}" for m in monthly_data],
                "records_generated": len(planning_records),
                "monthly_summary": monthly_data,
                "planning_records": planning_records[:5]  # Preview first 5
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error exporting monthly for Planning: {e}")
        return [TextContent(type="text", text=f"Error exporting monthly for Planning: {str(e)}")]


async def sync_to_planning(args: dict, config: dict) -> list[TextContent]:
    """Sync monthly forecast data to Oracle Planning Cloud."""
    try:
        start_date = datetime.strptime(args["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(args["end_date"], "%Y-%m-%d")
        scenario = args.get("scenario", "Forecast")
        load_method = args.get("load_method", "REPLACE")
        preview_only = args.get("preview_only", False)

        if end_date < start_date:
            return [TextContent(type="text", text="Error: End date must be after start date")]

        # Generate daily forecasts
        forecast = []
        running_balance = config["opening_cash_balance"]
        current_date = start_date

        while current_date <= end_date:
            inflows = calculate_daily_inflows(current_date, config)
            outflows = calculate_daily_outflows(current_date, config)

            total_inflows = sum(inflows.values())
            total_outflows = sum(outflows.values())
            net_cash_flow = total_inflows - total_outflows
            running_balance += net_cash_flow

            forecast.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "opening_balance": running_balance - net_cash_flow,
                "inflow_details": inflows,
                "outflow_details": outflows,
                "total_inflows": total_inflows,
                "total_outflows": total_outflows,
                "net_cash_flow": net_cash_flow,
                "closing_balance": running_balance
            })

            current_date += timedelta(days=1)

        # Aggregate to monthly
        monthly_data = aggregate_daily_to_monthly(forecast, config)

        # Format for Planning
        planning_records = format_for_planning_import(monthly_data, config, scenario)

        if preview_only:
            result = {
                "status": "preview",
                "message": "Preview mode - no data synced to Planning",
                "scenario": scenario,
                "load_method": load_method,
                "periods": [f"{m['year']}:{m['period']}" for m in monthly_data],
                "records_to_load": len(planning_records),
                "monthly_summary": monthly_data,
                "sample_records": planning_records[:10]
            }
        else:
            # Get Planning client and sync
            planning = get_planning_client(config)
            sync_result = planning.load_data(planning_records, load_method)

            # Save sync log
            log_filename = f"planning_sync_{args['start_date']}_{args['end_date']}.json"
            log_filepath = DATA_DIR / log_filename
            with open(log_filepath, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "scenario": scenario,
                    "load_method": load_method,
                    "periods": [f"{m['year']}:{m['period']}" for m in monthly_data],
                    "records_loaded": len(planning_records),
                    "sync_result": sync_result
                }, f, indent=2)

            result = {
                "status": "success",
                "message": f"Successfully synced {len(planning_records)} records to Planning",
                "scenario": scenario,
                "load_method": load_method,
                "periods": [f"{m['year']}:{m['period']}" for m in monthly_data],
                "records_loaded": len(planning_records),
                "job_id": sync_result.get("job_id"),
                "log_file": str(log_filepath)
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error syncing to Planning: {e}")
        return [TextContent(type="text", text=f"Error syncing to Planning: {str(e)}")]


async def get_planning_actuals(args: dict, config: dict) -> list[TextContent]:
    """Fetch last month's actuals from Oracle Planning for baselining forecast."""
    try:
        period = args["period"]
        entity = args.get("entity", config.get("entity_id", "E501"))

        # Get Planning client
        planning = get_planning_client(config)

        # Fetch actuals
        pov = {
            "Scenario": "Actual",
            "Entity": entity,
            "Version": "Final",
            "Period": period
        }

        actuals_result = planning.fetch_data(
            pov=pov,
            rows=list(INFLOW_CATEGORIES.keys()) + list(OUTFLOW_CATEGORIES.keys()),
            columns=["Amount"]
        )

        actuals_data = actuals_result.get("data", [])

        # Organize by account
        inflows = {}
        outflows = {}
        for record in actuals_data:
            account = record.get("Account", "")
            amount = record.get("Amount", 0)
            if account in INFLOW_CATEGORIES:
                inflows[account] = {
                    "name": INFLOW_CATEGORIES[account],
                    "amount": amount
                }
            elif account in OUTFLOW_CATEGORIES:
                outflows[account] = {
                    "name": OUTFLOW_CATEGORIES[account],
                    "amount": abs(amount)
                }

        total_inflows = sum(i["amount"] for i in inflows.values())
        total_outflows = sum(o["amount"] for o in outflows.values())

        result = {
            "status": "success",
            "period": period,
            "entity": entity,
            "actuals": {
                "inflows": inflows,
                "outflows": outflows,
                "total_inflows": round(total_inflows, 2),
                "total_outflows": round(total_outflows, 2),
                "net_cash_flow": round(total_inflows - total_outflows, 2)
            },
            "records_fetched": len(actuals_data),
            "use_for": "Baseline data to calibrate forecast accuracy"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error fetching Planning actuals: {e}")
        return [TextContent(type="text", text=f"Error fetching Planning actuals: {str(e)}")]


async def main():
    """Run the MCP server."""
    logger.info("Starting Hotel Cash Flow Forecasting MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
