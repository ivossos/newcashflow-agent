#!/usr/bin/env python3
"""
HTTP Server wrapper for Cloud Run deployment.

This module wraps the MCP server to expose it via HTTP/SSE transport
and REST API endpoints for ChatGPT Custom GPT integration.
"""

import os
import json
import logging
from datetime import datetime

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Import the MCP server components
from cashflow_mcp_server import (
    server,
    load_hotel_data,
    generate_daily_forecast,
    get_cash_position,
    run_scenario,
    validate_forecast,
    export_report,
    optimize_pricing,
    get_events_calendar,
    get_competitor_analysis,
    sync_rates_to_opera,
    fetch_opera_rates,
    get_opera_inventory,
    INFLOW_CATEGORIES,
    OUTFLOW_CATEGORIES,
    DATA_DIR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cashflow-http-server")


async def health_check(request):
    """Health check endpoint for Cloud Run."""
    return JSONResponse({
        "status": "healthy",
        "service": "cashflow-mcp-server",
        "timestamp": datetime.now().isoformat()
    })


async def info(request):
    """Server info endpoint."""
    config = load_hotel_data()
    return JSONResponse({
        "name": "Hotel Cash Flow Forecasting MCP Server",
        "version": "1.0.0",
        "hotel": config.get("hotel_name", "Unknown"),
        "capabilities": [
            "generate_daily_forecast",
            "get_cash_position",
            "run_scenario",
            "validate_forecast",
            "export_report",
            "optimize_pricing",
            "get_events",
            "get_competitor_rates",
            "sync_rates_to_opera",
            "fetch_opera_rates",
            "get_opera_inventory"
        ]
    })


async def extract_text_content(result):
    """Extract text content from MCP TextContent result."""
    if result and len(result) > 0:
        text = result[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}
    return {"error": "No result"}


# REST API Endpoints for ChatGPT

async def api_forecast(request: Request):
    """Generate daily cash flow forecast."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await generate_daily_forecast(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_cash_position(request: Request):
    """Get current cash position."""
    try:
        body = await request.json() if request.method == "POST" else {}
        config = load_hotel_data()
        result = await get_cash_position(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_scenario(request: Request):
    """Run what-if scenario analysis."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await run_scenario(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_validate(request: Request):
    """Validate forecast against actuals."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await validate_forecast(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_export(request: Request):
    """Export cash flow report."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await export_report(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_pricing(request: Request):
    """Calculate optimal room rates using dynamic pricing."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await optimize_pricing(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_events(request: Request):
    """Get local events calendar."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await get_events_calendar(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_competitors(request: Request):
    """Get competitor rate analysis."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await get_competitor_analysis(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_sync_opera(request: Request):
    """Sync rates to Oracle Opera PMS."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await sync_rates_to_opera(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_fetch_opera(request: Request):
    """Fetch rates from Oracle Opera PMS."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await fetch_opera_rates(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def api_opera_inventory(request: Request):
    """Get room inventory from Oracle Opera PMS."""
    try:
        body = await request.json()
        config = load_hotel_data()
        result = await get_opera_inventory(body, config)
        return JSONResponse(await extract_text_content(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def openapi_schema(request: Request):
    """Return OpenAPI schema for ChatGPT Custom GPT."""
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "Hotel Cash Flow Forecasting API",
            "description": "API for hotel cash flow forecasting, dynamic pricing optimization, and Opera PMS integration",
            "version": "1.0.0"
        },
        "servers": [
            {
                "url": "https://cashflow-mcp-241840460713.us-central1.run.app"
            }
        ],
        "paths": {
            "/api/forecast": {
                "post": {
                    "operationId": "generateForecast",
                    "summary": "Generate daily cash flow forecast",
                    "description": "Generate cash flow forecast for a specified date range with projected inflows, outflows, and net cash position",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Forecast generated successfully"
                        }
                    }
                }
            },
            "/api/cash-position": {
                "post": {
                    "operationId": "getCashPosition",
                    "summary": "Get current cash position",
                    "description": "Get current cash position including opening balance, today's movements, and projected closing balance",
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "as_of_date": {
                                            "type": "string",
                                            "description": "Date to check position (YYYY-MM-DD). Defaults to today."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Cash position retrieved successfully"
                        }
                    }
                }
            },
            "/api/scenario": {
                "post": {
                    "operationId": "runScenario",
                    "summary": "Run what-if scenario analysis",
                    "description": "Run what-if scenario analysis on cash flow by adjusting occupancy, rates, or expenses",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["scenario_name", "start_date", "end_date"],
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
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Scenario analysis completed successfully"
                        }
                    }
                }
            },
            "/api/pricing": {
                "post": {
                    "operationId": "optimizePricing",
                    "summary": "Calculate optimal room rates",
                    "description": "Calculate optimal room rates using dynamic pricing based on occupancy, day of week, seasonality, lead time, local events, and competitor rates",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                            "description": "Current occupancy percentage (0-100)"
                                        },
                                        "lead_days": {
                                            "type": "integer",
                                            "description": "Days until guest arrival (0 = same day booking)"
                                        },
                                        "include_breakdown": {
                                            "type": "boolean",
                                            "description": "Include detailed breakdown of pricing factors",
                                            "default": True
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Pricing optimization completed successfully"
                        }
                    }
                }
            },
            "/api/events": {
                "post": {
                    "operationId": "getEvents",
                    "summary": "Get local events calendar",
                    "description": "Get local events that impact hotel demand and pricing",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Events retrieved successfully"
                        }
                    }
                }
            },
            "/api/competitors": {
                "post": {
                    "operationId": "getCompetitorRates",
                    "summary": "Get competitor rate analysis",
                    "description": "Get competitor hotel rates for market comparison and positioning",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["date"],
                                    "properties": {
                                        "date": {
                                            "type": "string",
                                            "description": "Date to check competitor rates (YYYY-MM-DD)"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Competitor analysis retrieved successfully"
                        }
                    }
                }
            },
            "/api/opera/sync": {
                "post": {
                    "operationId": "syncRatesToOpera",
                    "summary": "Sync rates to Oracle Opera PMS",
                    "description": "Sync optimized dynamic pricing rates to Oracle Opera PMS",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                            "description": "Opera rate code to update",
                                            "default": "BAR"
                                        },
                                        "room_type": {
                                            "type": "string",
                                            "description": "Room type code",
                                            "default": "STD"
                                        },
                                        "preview_only": {
                                            "type": "boolean",
                                            "description": "If true, shows rates without syncing",
                                            "default": False
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Rates synced successfully"
                        }
                    }
                }
            },
            "/api/opera/rates": {
                "post": {
                    "operationId": "fetchOperaRates",
                    "summary": "Fetch rates from Oracle Opera PMS",
                    "description": "Fetch current rates from Oracle Opera PMS for comparison with dynamic pricing recommendations",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                            "description": "Opera rate code to fetch",
                                            "default": "BAR"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Opera rates fetched successfully"
                        }
                    }
                }
            },
            "/api/opera/inventory": {
                "post": {
                    "operationId": "getOperaInventory",
                    "summary": "Get room inventory from Opera",
                    "description": "Get room inventory and occupancy data from Oracle Opera PMS",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
                                    "properties": {
                                        "start_date": {
                                            "type": "string",
                                            "description": "Start date in YYYY-MM-DD format"
                                        },
                                        "end_date": {
                                            "type": "string",
                                            "description": "End date in YYYY-MM-DD format"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Inventory retrieved successfully"
                        }
                    }
                }
            },
            "/api/export": {
                "post": {
                    "operationId": "exportReport",
                    "summary": "Export cash flow report",
                    "description": "Export cash flow forecast report in various formats",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["start_date", "end_date"],
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
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Report exported successfully"
                        }
                    }
                }
            }
        }
    }
    return JSONResponse(schema)


# CORS middleware for browser access
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
]

# Create Starlette app with routes
app = Starlette(
    debug=False,
    routes=[
        # Health and info
        Route("/", health_check),
        Route("/health", health_check),
        Route("/info", info),
        Route("/openapi.json", openapi_schema),

        # REST API endpoints for ChatGPT
        Route("/api/forecast", api_forecast, methods=["POST"]),
        Route("/api/cash-position", api_cash_position, methods=["POST"]),
        Route("/api/scenario", api_scenario, methods=["POST"]),
        Route("/api/validate", api_validate, methods=["POST"]),
        Route("/api/export", api_export, methods=["POST"]),
        Route("/api/pricing", api_pricing, methods=["POST"]),
        Route("/api/events", api_events, methods=["POST"]),
        Route("/api/competitors", api_competitors, methods=["POST"]),
        Route("/api/opera/sync", api_sync_opera, methods=["POST"]),
        Route("/api/opera/rates", api_fetch_opera, methods=["POST"]),
        Route("/api/opera/inventory", api_opera_inventory, methods=["POST"]),
    ],
    middleware=middleware,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting HTTP server on port {port}")

    uvicorn.run(app, host="0.0.0.0", port=port)
