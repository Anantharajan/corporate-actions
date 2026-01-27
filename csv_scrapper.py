import requests, time
from datetime import datetime, timedelta

BASE = "https://www.nseindia.com"
API  = "https://www.nseindia.com/api/corporates-CorporateActions"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")

def fetch_corporate_actions_csv(from_dt, to_dt, segment="equities", max_retries=3):
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        # Do NOT set Cookie manually; let Session manage it to avoid duplicates.
    })

    # Warm-up: visit base and relevant page to obtain Akamai/Adobe cookies.
    for url in [BASE, f"{BASE}/companies-listing/corporate-filings-actions"]:
        r0 = sess.get(url, timeout=20)
        r0.raise_for_status()
        time.sleep(0.8)  # small human-like pause

    params = {
        "index": segment,
        "from_date": from_dt.strftime("%d-%m-%Y"),
        "to_date": to_dt.strftime("%d-%m-%Y"),
        "csv": "true",
    }

    # Add a realistic Referer before hitting API
    hdrs = {
        "Referer": f"{BASE}/companies-listing/corporate-filings-actions",
        "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.8",
    }

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = sess.get(API, params=params, headers=hdrs, timeout=30, allow_redirects=True)
            if r.status_code == 401:
                # Re-warm cookies and retry
                sess.get(BASE, timeout=20)
                time.sleep(0.8)
                last_err = requests.HTTPError(f"401 on attempt {attempt}")
                continue
            r.raise_for_status()
            # Basic sanity check: CSV should start with headers
            if r.text[:128].count(",") == 0 and "html" in r.headers.get("Content-Type","").lower():
                raise ValueError("Unexpected non-CSV response")
            return r.content
        except Exception as e:
            last_err = e
            time.sleep(1.2)  # backoff
    raise last_err

if __name__ == "__main__":
    today = datetime.now()
    to = today + timedelta(days=30)
    csv_bytes = fetch_corporate_actions_csv(today, to)
    with open("corporate_actions_upcoming.csv", "wb") as f:
        f.write(csv_bytes)
