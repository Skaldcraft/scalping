import yfinance as yf

def check_xauusd():
    df = yf.Ticker("XAUUSD=X").history(period="1mo", interval="1d")
    print("XAUUSD=X daily data (last month):")
    print(df)
    if df.empty:
        print("\nNo data returned. Yahoo Finance may not provide XAUUSD=X at this time.")
    else:
        print(f"\nRows returned: {len(df)}")

if __name__ == "__main__":
    check_xauusd()
