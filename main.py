from fastapi import FastAPI
import yfinance as yf
from scipy.optimize import fsolve
import time

app = FastAPI()

# -------------------------------
# DATA FETCH WITH ERROR HANDLING
# -------------------------------

def get_yahoo_data(ticker):
    try:
        time.sleep(2)  # helps reduce rate limiting

        stock = yf.Ticker(ticker)

        financials = stock.financials
        cashflow = stock.cashflow
        info = stock.info

        net_profit = financials.loc["Net Income"].iloc[0]
        eps = info.get("trailingEps")

        # Flexible CFO detection
        if "Total Cash From Operating Activities" in cashflow.index:
            cfo = cashflow.loc["Total Cash From Operating Activities"].iloc[0]
        elif "Operating Cash Flow" in cashflow.index:
            cfo = cashflow.loc["Operating Cash Flow"].iloc[0]
        else:
            raise Exception("CFO not found")

        # Flexible Capex detection
        if "Capital Expenditures" in cashflow.index:
            capex = abs(cashflow.loc["Capital Expenditures"].iloc[0])
        elif "Capital Expenditure" in cashflow.index:
            capex = abs(cashflow.loc["Capital Expenditure"].iloc[0])
        else:
            raise Exception("Capex not found")

        return net_profit, eps, cfo, capex

    except Exception as e:
        print("Yahoo fetch failed:", e)
        return None, None, None, None


# -------------------------------
# REVERSE DCF SOLVER
# -------------------------------

def solve_growth(price, e0, multiple, r, years):
    def equation(g):
        return (e0 * (1 + g)**years * multiple) / (1 + r)**years - price

    return fsolve(equation, 0.1)[0]


# -------------------------------
# MAIN API ENDPOINT
# -------------------------------

@app.get("/analyze")
def analyze(company: str, price: float, metric: str, discount_rate: float,
            m5: float, m10: float, m15: float, m20: float):

    net_profit, eps, cfo, capex = get_yahoo_data(company)

    # Handle rate limit / failure
    if net_profit is None or eps is None:
        return {
            "error": "Data fetch failed (Yahoo rate limit). Try again after some time or use another stock."
        }

    shares = net_profit / eps
    fcf = cfo - capex
    market_cap = price * shares

    # Select metric
    if metric == "PAT":
        e0 = net_profit / shares
        current_multiple = market_cap / net_profit
    elif metric == "FCF":
        e0 = fcf / shares
        current_multiple = market_cap / fcf
    else:  # CFO
        e0 = cfo / shares
        current_multiple = market_cap / cfo

    # Solve implied growth
    g5 = solve_growth(price, e0, m5, discount_rate, 5)
    g10 = solve_growth(price, e0, m10, discount_rate, 10)
    g15 = solve_growth(price, e0, m15, discount_rate, 15)
    g20 = solve_growth(price, e0, m20, discount_rate, 20)

    return {
        "current_multiple": current_multiple,
        "growth": {
            "5Y": g5,
            "10Y": g10,
            "15Y": g15,
            "20Y": g20
        }
    }


# -------------------------------
# ROOT ENDPOINT (OPTIONAL)
# -------------------------------

@app.get("/")
def home():
    return {"message": "Reverse DCF API is running 🚀"}
