# Hotel Cash Flow Forecasting MCP - 20 Minute Demo Script

## Demo Overview
- **Hotel**: 501-L7 Chicago Hotel (Entity E501)
- **Region**: Illinois (R131)
- **Integration**: Oracle Planning + Oracle Opera PMS

---

## 1. Opening - Current Position (2 min)

```
What's the current cash position for our Chicago hotel today?
```

```
Show me today's cash position with all the revenue and expense breakdowns
```

---

## 2. Daily Forecast - Week Ahead (3 min)

```
Generate a cash flow forecast for the next 7 days for the L7 Chicago Hotel
```

```
I need to see our projected cash flow from January 15 to January 31, 2026. We have payroll coming up on the 15th and vendor payments on the 25th - will we stay above our minimum reserve?
```

---

## 3. Monthly Planning View (2 min)

```
Generate a 30-day cash flow forecast starting today. I need to present this to the CFO for our monthly finance review.
```

---

## 4. Scenario Analysis - Business Impact (4 min)

### Scenario A - Low Season Impact
```
Run a scenario called "February Low Season" from February 1 to February 28, 2026 with occupancy down 15% and room rates reduced by 10%
```

### Scenario B - Cost Pressures
```
Create a scenario named "Rising Costs Q1" for the next 30 days. Assume expenses increase by 12% due to inflation while occupancy stays the same.
```

### Scenario C - High Season Opportunity
```
Run a what-if scenario called "Summer Peak" from June 1 to June 30, 2026 with 20% higher occupancy and 15% rate increase
```

---

## 5. Forecast Validation (2 min)

```
Validate yesterday's forecast against our actual results: we had $42,500 in total inflows and $28,300 in outflows
```

```
How accurate was our forecast for January 14? Actual inflows were $45,200 and outflows were $31,800
```

---

## 6. Dynamic Pricing Optimization (3 min)

```
Optimize room pricing for the next 14 days - we're currently at 78% occupancy
```

```
What should our room rates be during the Chicago Auto Show from January 20-25?
```

```
Calculate optimal pricing for this weekend with 85% occupancy and same-day bookings
```

---

## 7. Events & Competitor Analysis (2 min)

```
What local events are happening in Chicago this month that could impact our hotel demand?
```

```
Show me competitor rates for this Saturday - I want to see how we compare to Marriott and Hilton
```

```
Get all festival and sports events for the summer months
```

---

## 8. Opera PMS Integration (4 min)

### Fetch Current Rates from Opera
```
Fetch current rates from Opera for the next 14 days and compare with our recommendations
```

### Get Occupancy Data
```
Get Opera inventory and occupancy for this week
```

### Preview Rate Sync
```
Preview rate sync to Opera for the Chicago Auto Show January 20-25 - don't push yet
```

### Push Rates to Opera
```
Sync optimized rates to Opera for January 20-25
```

### Compare Opera vs Recommended
```
Show which days need rate increases based on Opera current rates vs our dynamic pricing
```

---

## 9. Export Reports for Stakeholders (2 min)

```
Export a cash flow summary report for January 2026 - I need to send this to our regional finance team
```

```
Generate a CSV export of the cash flow forecast for the next 2 weeks so I can import it into our Planning system
```

```
Create a JSON export of the forecast from January 15 to February 15 for integration with Oracle Planning
```

---

## Quick Reference Card

| Feature | Sample Prompt |
|---------|---------------|
| **Cash Position** | "What's our cash position today?" |
| **7-Day Forecast** | "Forecast cash flow for the next week" |
| **30-Day Forecast** | "Generate monthly cash flow forecast" |
| **Scenario - Pessimistic** | "Run scenario with 20% lower occupancy" |
| **Scenario - Optimistic** | "What if rates increase 15%?" |
| **Dynamic Pricing** | "Optimize pricing for next 14 days at 80% occupancy" |
| **Events Calendar** | "What events are in Chicago this month?" |
| **Competitor Rates** | "Show competitor rates for Saturday" |
| **Opera - Fetch Rates** | "Fetch current rates from Opera for next 14 days" |
| **Opera - Inventory** | "Get Opera inventory for this week" |
| **Opera - Sync Rates** | "Sync optimized rates to Opera for next 7 days" |
| **Opera - Preview** | "Preview rate sync to Opera without pushing" |
| **Validate Accuracy** | "Compare forecast to actuals: $45K in, $30K out" |
| **Export Summary** | "Export cash flow report for this month" |

---

## Demo Talking Points

1. **Real-time visibility** into hotel cash position
2. **Account codes** (410000, 710100, etc.) align with Oracle Planning dimensions
3. **Dynamic Pricing Engine** - AI-optimized rates based on 6 factors
4. **Local Events** - Chicago Auto Show, Lollapalooza, Marathon, etc.
5. **Competitor Intelligence** - Compare with Marriott, Hilton, Hyatt
6. **Opera PMS Integration** - Fetch rates, sync pricing, get occupancy
7. **What-if scenarios** for strategic planning and risk assessment
8. **Validation** to track and improve forecast accuracy over time
9. **Multiple export formats** (Summary, CSV, JSON) for stakeholder reporting

---

## Dynamic Pricing Factors

| Factor | Adjustment Range |
|--------|------------------|
| **Occupancy** | -25% (low) to +50% (sold out) |
| **Day of Week** | -12% (Tue) to +25% (Sat) |
| **Seasonality** | -20% (Jan/Feb) to +35% (Dec) |
| **Lead Time** | -15% (far advance) to +30% (same day) |
| **Local Events** | +15% to +60% (major events) |
| **Competitor Rates** | Capped at 15% above market |

### Chicago Events Calendar (Sample)
- **Jan 20-25**: Chicago Auto Show (+40-45%)
- **Feb 14**: Valentine's Day (+25%)
- **Mar 14-17**: St. Patrick's Day (+30-35%)
- **Aug 1-4**: Lollapalooza (+45-50%)
- **Oct 11**: Chicago Marathon (+40%)
- **Dec 31**: New Year's Eve (+50%)

---

## Hotel Configuration (Planning Aligned)

| Parameter | Value |
|-----------|-------|
| Hotel Name | 501-L7 Chicago Hotel |
| Entity ID | E501 |
| Region | R131 (Illinois) |
| Cost Center | CC1121 |
| Room Count | 250 |
| Average Daily Rate | $189.00 |
| Average Occupancy | 75% |
| Opening Cash Balance | $350,000 |
| Minimum Cash Reserve | $75,000 |

---

## Account Codes Reference

### Revenue (Inflows)
| Account | Description |
|---------|-------------|
| 410000 | Room Revenue |
| 420000 | F&B Revenue |
| 430000 | Banquet & Events |
| 440000 | Spa & Wellness |
| 450000 | Other Operating Revenue |

### Expenses (Outflows)
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
