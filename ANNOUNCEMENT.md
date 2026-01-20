# New MCP Server: Hotel Cash Flow Forecasting

Hi Team,

I'm excited to share a new MCP server I've created for **hotel cash flow forecasting**. This tool allows you to forecast and analyze hotel daily cash flows using natural language conversations in Claude Desktop.

## What It Does

- **Cash Position**: Get real-time view of hotel cash balances
- **Daily Forecasting**: Generate up to 90-day cash flow projections
- **Scenario Analysis**: Run what-if scenarios (occupancy changes, rate adjustments, cost increases)
- **Forecast Validation**: Track forecast accuracy against actuals
- **Export Reports**: Generate Summary, CSV, or JSON reports

## Oracle Planning Integration

The server is fully aligned with our Planning dimensions and account codes:
- Entity: E501 (501-L7 Chicago Hotel)
- Accounts: 410000 (Room Revenue), 710100 (Payroll), etc.
- All 10 Planning dimensions supported

## How to Use

1. Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "cashflow-forecast": {
      "command": "python",
      "args": ["C:/path/to/cashflow_mcp_server.py"]
    }
  }
}
```

2. Restart Claude Desktop

3. Start asking questions:
   - "What's our cash position today?"
   - "Generate a 30-day cash flow forecast"
   - "Run a scenario with 20% lower occupancy"

## Repository

**GitHub**: https://github.com/ivossos/cashflow-mcp

The repo includes:
- Full source code
- Installation instructions
- Demo script for presentations
- One-pager overview

## Demo Available

I've prepared a 15-minute demo script if anyone wants a walkthrough. Let me know!

---

Feel free to reach out if you have questions or suggestions.

Best,
Ivo
