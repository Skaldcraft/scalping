import yfinance as yf

def check_gold_futures():
    gold = yf.Ticker("GC=F")
    data = gold.history(period="1mo")
    print("GC=F (Gold Futures) daily data (last month):")
    print(data)
    if data.empty:
        print("\nNo data returned. Yahoo Finance may not provide GC=F at this time.")
    else:
        print(f"\nRows returned: {len(data)}")

if __name__ == "__main__":
    check_gold_futures()
