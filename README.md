# Hotel Cash Flow Forecasting MCP Server

AI-powered daily cash flow forecasting for hotel operations using the Model Context Protocol (MCP). Seamlessly integrated with Oracle EPM Planning dimensions and account codes.

## Features

- **Real-time Cash Position** - View current balances, inflows, outflows, and projections
- **Daily Forecasting** - Generate forecasts up to 90 days with built-in seasonality
- **Scenario Analysis** - Run what-if scenarios for occupancy, rates, and expenses
- **Forecast Validation** - Compare forecasts vs actuals to track accuracy
- **Multi-Format Export** - Summary, CSV, and JSON reports for stakeholders

## Installation

### Prerequisites

- Python 3.10+
- Claude Desktop

### Setup

1. Clone the repository:
```bash
git clone https://github.com/ivossos/cashflow-mcp.git
cd cashflow-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "cashflow-forecast": {
      "command": "python",
      "args": ["C:/path/to/cashflow-mcp/cashflow_mcp_server.py"]
    }
  }
}
```

4. Restart Claude Desktop

## Usage

### Get Cash Position
```
What's the current cash position for our hotel today?
```

### Generate Forecast
```
Generate a cash flow forecast for the next 30 days
```

### Run Scenarios
```
Run a scenario called "Low Season" with occupancy down 15% and rates reduced 10% for February
```

### Validate Forecast
```
Validate yesterday's forecast: actual inflows $45,000 and outflows $28,000
```

### Export Reports
```
Export a cash flow summary report for January 2026
Export forecast as CSV for the next 2 weeks
```

## Tools

| Tool | Description |
|------|-------------|
| `generate_daily_forecast` | Generate cash flow forecast for a date range |
| `get_cash_position` | Get current cash position and balances |
| `run_scenario` | Run what-if scenario analysis |
| `validate_forecast` | Compare forecast vs actuals |
| `export_report` | Export reports (JSON, CSV, Summary) |

## Oracle Planning Integration

Aligned with EPM Planning dimensions:

| Dimension | Default Value |
|-----------|---------------|
| Entity | E501 (501-L7 Chicago Hotel) |
| Region | R131 (Illinois) |
| Cost Center | CC1121 |
| Scenario | Actual |
| Version | Final |
| Currency | USD |
| Fiscal Year | FY25 |

### Account Codes

**Revenue (Inflows)**
| Account | Description |
|---------|-------------|
| 410000 | Room Revenue |
| 420000 | F&B Revenue |
| 430000 | Banquet & Events |
| 440000 | Spa & Wellness |
| 450000 | Other Operating Revenue |

**Expenses (Outflows)**
| Account | Description |
|---------|-------------|
| 710100 | Salaries & Wages |
| 710110 | Benefits & Insurance |
| 710120 | Utilities Expense |
| 710130 | Repairs & Maintenance |
| 710140 | Marketing & Promotions |
| 720000 | F&B Cost of Sales |
| 730000 | Vendor & Supplier Payments |
| 911000 | Interest Expense |
| 912000 | Tax Expense |

## Default Hotel Configuration

| Parameter | Value |
|-----------|-------|
| Hotel Name | 501-L7 Chicago Hotel |
| Room Count | 250 |
| Average Daily Rate | $189.00 |
| Average Occupancy | 75% |
| Opening Cash Balance | $350,000 |
| Minimum Cash Reserve | $75,000 |

### Seasonality

- **High Season**: June, July, August, December (+35%)
- **Low Season**: January, February, November (-35%)
- **Weekend Adjustment**: +15%

## Project Structure

```
cashflow-mcp/
├── cashflow_mcp_server.py   # Main MCP server
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project configuration
├── DEMO_SCRIPT.md          # 15-minute demo prompts
├── ONE_PAGER.md            # Executive summary
└── data/                   # Generated data files
    └── hotel_config.json   # Hotel configuration
```

## Demo

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for a complete 15-minute demo with sample prompts.

## License

MIT

## Author

Digital IMS Cloud - Oracle EPM Solutions
