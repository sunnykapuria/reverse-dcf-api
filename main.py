from fastapi import FastAPI
import yfinance as yf
from scipy.optimize import fsolve

app = FastAPI()

def get_yahoo_data(ticker):
    stock = yf.Ticker(ticker)

    financials = stock.financials
    cashflow = stock.cashflow
    info = stock.info

    net_profit = financials.loc["Net Income"].iloc[0]
    eps = info.get("trailingEps")

    # Flexible matching for CFO
    if "Total Cash From Operating Activities" in cashflow.index:
        cfo = cashflow.loc["Total Cash From Operating Activities"].iloc[0]
    elif "Operating Cash Flow" in cashflow.index:
        cfo = cashflow.loc["Operating Cash Flow"].iloc[0]
    else:
        raise Exception("CFO not found")

    # Flexible matching for Capex
    if "Capital Expenditures" in cashflow.index:
        capex = abs(cashflow.loc["Capital Expenditures"].iloc[0])
    elif "Capital Expenditure" in cashflow.index:
        capex = abs(cashflow.loc["Capital Expenditure"].iloc[0])
    else:
        raise Exception("Capex not found")

    return net_profit, eps, cfo, capex

def solve_growth(price, e0, multiple, r, years):
    def equation(g):
        return (e0 * (1 + g)**years * multiple) / (1 + r)**years - price

    return fsolve(equation, 0.1)[0]

@app.get("/analyze")
def analyze(company: str, price: float, metric: str, discount_rate: float,
            m5: float, m10: float, m15: float, m20: float):

    try:
        net_profit, eps, cfo, capex = get_yahoo_data(company)

        shares = net_profit / eps
        fcf = cfo - capex
        market_cap = price * shares

        if metric == "PAT":
            e0 = net_profit / shares
            current_multiple = market_cap / net_profit
        elif metric == "FCF":
            e0 = fcf / shares
            current_multiple = market_cap / fcf
        else:
            e0 = cfo / shares
            current_multiple = market_cap / cfo

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

    except Exception as e:
        return {"error": str(e)}