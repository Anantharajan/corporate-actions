# build_actions_and_index.py
# HTML + JSON generator with SEARCH, CSV EXPORT, EX-DATE HIGHLIGHT (<=7 days)

import csv, re, json, html
from datetime import datetime, date
from pathlib import Path
import subprocess

CSV_IN   = Path("corporate_actions_upcoming.csv")
JSON_OUT = Path("corporate_actions.json")
HTML_OUT = Path("index.html")

# ---------------- Utilities ----------------

def to_iso(d):
    d = (d or "").strip()
    if not d or d == "-":
        return ""
    return datetime.strptime(d, "%d-%b-%Y").strftime("%Y-%m-%d")

def esc(s):
    return html.escape(str(s)) if s is not None else ""

# ---------------- Parsing ----------------

def parse_purpose(p):
    p = (p or "").strip()

    is_div = "Dividend" in p
    div_cat = (
        "Interim" if "Interim" in p else
        "Final" if "Final" in p else
        "Special" if "Special" in p else ""
    )

    m_amt = re.search(r"\bR(?:s|e)\s*\.?\s*([0-9]+(?:\.[0-9]+)?)", p, re.I)
    div_amt = f"₹{m_amt.group(1)}" if m_amt else "-"

    m_bonus = re.search(r"\bBonus\s+(\d+)\s*:\s*(\d+)", p, re.I)
    bonus_ratio = f"{m_bonus.group(1)}:{m_bonus.group(2)}" if m_bonus else ""

    is_rights = p.lower().startswith("rights")

    m_split = re.search(r"From\s*R(?:s)?\s*([0-9]+).+?To\s*R(?:s)?\s*([0-9]+)", p, re.I)
    split_from = f"₹{m_split.group(1)}" if m_split else "-"
    split_to   = f"₹{m_split.group(2)}" if m_split else "-"

    is_split = "split" in p.lower() or "sub-division" in p.lower()
    is_interest = "interest payment" in p.lower()

    return {
        "is_div": is_div,
        "div_cat": div_cat,
        "div_amt": div_amt,
        "bonus_ratio": bonus_ratio,
        "is_split": is_split,
        "split_from": split_from,
        "split_to": split_to,
        "is_rights": is_rights,
        "is_interest": is_interest,
    }

# ---------------- Load CSV ----------------

def load_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

# ---------------- JSON Builder ----------------

def build_json(rows):
    divs, bonus, splits, others = [], [], [], []

    for r in rows:
        sym = (r.get("SYMBOL") or "").strip()
        name = (r.get("COMPANY NAME") or "").strip()
        purpose = (r.get("PURPOSE") or "").strip()
        ex = to_iso(r.get("EX-DATE"))
        rec = to_iso(r.get("RECORD DATE"))
        p = parse_purpose(purpose)

        if p["is_interest"]:
            continue

        if p["bonus_ratio"]:
            bonus.append({
                "name": name or sym, "symbol": sym,
                "ratio": p["bonus_ratio"], "ex": ex, "rec": rec
            })

        elif p["is_split"]:
            splits.append({
                "name": name or sym, "symbol": sym,
                "action": "Face Value Split",
                "from": p["split_from"], "to": p["split_to"],
                "ex": ex, "rec": rec
            })

        elif p["is_rights"]:
            others.append({
                "name": name or sym, "symbol": sym,
                "action": purpose, "from": "-", "to": "-",
                "ex": ex, "rec": rec
            })

        elif p["is_div"]:
            divs.append({
                "name": name or sym, "symbol": sym,
                "amount": p["div_amt"], "cat": p["div_cat"] or "-",
                "ex": ex, "rec": rec
            })

        else:
            others.append({
                "name": name or sym, "symbol": sym,
                "action": purpose or "Other",
                "from": "-", "to": "-",
                "ex": ex, "rec": rec
            })

    def s(items):
        return sorted(items, key=lambda x: (x["ex"] == "", x["ex"]))

    return {
        "dividends": s(divs),
        "bonuses": s(bonus),
        "splits": s(splits),
        "others": s(others),
    }

# ---------------- HTML Table ----------------

def html_table(headers, rows, caption):
    return f"""
<table>
<caption>{esc(caption)}</caption>
<thead><tr>{''.join(f'<th>{esc(h)}</th>' for h in headers)}</tr></thead>
<tbody>
{''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in r) + '</tr>' for r in rows)}
</tbody>
</table>
"""

# ---------------- HTML Builder ----------------

def build_index_html(data):

    div_rows = [
        [f"{d['name']} ({d['symbol']})", "Dividend", d["amount"], d["cat"], d["ex"], d["rec"]]
        for d in data["dividends"]
    ]

    bonus_rows = [
        [f"{b['name']} ({b['symbol']})", b["ratio"], b["ex"], b["rec"]]
        for b in data["bonuses"]
    ]

    split_rows = (
        [[f"{s['name']} ({s['symbol']})", s["action"], s["from"], s["to"], s["ex"], s["rec"]] for s in data["splits"]]
        + [[f"{o['name']} ({o['symbol']})", o["action"], o["from"], o["to"], o["ex"], o["rec"]] for o in data["others"]]
    )

    css = """
<style>
:root {
  --bg: #0b1020;
  --card: #141a2e;
  --header-bg: #1b2240;
  --text: #e7ecf3;
  --accent: #bcd2ff;
  --highlight-bg: #2a3b1f;
  --highlight-text: #eaffc7;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  padding: 40px 20px;
  margin: 0;
}

.container {
  max-width: 1200px;
  margin: auto;
}

h1 { margin-bottom: 30px; font-weight: 300; letter-spacing: 1px; }

/* Table Styling */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 30px 0;
  background: var(--card);
  box-shadow: 0 4px 15px rgba(0,0,0,0.3);
  border-radius: 8px;
  overflow: hidden; /* Rounds the table corners */
}

caption {
  font-size: 22px;
  font-weight: 600;
  text-align: left;
  margin: 15px 0;
  color: var(--accent);
}

th, td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid #24304e;
}

th {
  background: var(--header-bg);
  color: var(--accent);
  text-transform: uppercase;
  font-size: 13px;
  letter-spacing: 0.5px;
  cursor: pointer;
}

/* Hover effect for rows */
tbody tr:hover { background: rgba(255,255,255,0.03); }

/* The 7-day Highlight */
tr.highlight td {
  background: var(--highlight-bg) !important;
  color: var(--highlight-text);
}

/* Controls Styling */
input#search {
  padding: 12px 15px;
  width: 100%;
  max-width: 400px;
  border-radius: 6px;
  border: 1px solid #24304e;
  background: var(--card);
  color: white;
  margin-bottom: 20px;
}

button#export {
  padding: 10px 20px;
  border-radius: 6px;
  border: none;
  background: #3d5afe;
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

button#export:hover { background: #536dfe; }
</style>
"""

    js = """
<script>
document.addEventListener("DOMContentLoaded", () => {

  // SEARCH
  const search = document.getElementById("search");
  search.addEventListener("input", () => {
    const q = search.value.toLowerCase();
    document.querySelectorAll("tbody tr").forEach(tr => {
      tr.style.display = tr.innerText.toLowerCase().includes(q) ? "" : "none";
    });
  });

  // SORT
  document.querySelectorAll("table").forEach(table => {
    table.querySelectorAll("th").forEach((th, idx) => {
      th.addEventListener("click", () => {
        const asc = !th.classList.contains("asc");
        table.querySelectorAll("th").forEach(h=>h.classList.remove("asc","desc"));
        th.classList.add(asc?"asc":"desc");

        const rows = [...table.tBodies[0].rows];
        rows.sort((a,b)=>{
          const A=a.cells[idx].innerText,B=b.cells[idx].innerText;
          return asc?A.localeCompare(B):B.localeCompare(A);
        });
        rows.forEach(r=>table.tBodies[0].appendChild(r));
      });
    });
  });

  // EX-DATE HIGHLIGHT <= 7 DAYS
  const today = new Date();
  document.querySelectorAll("tbody tr").forEach(tr=>{
    const cells=[...tr.cells];
    cells.forEach(c=>{
      if(/^\\d{4}-\\d{2}-\\d{2}$/.test(c.innerText)){
        const d=new Date(c.innerText);
        const diff=(d-today)/(1000*60*60*24);
        if(diff>=0 && diff<=7) tr.classList.add("highlight");
      }
    });
  });

  // CSV EXPORT
  document.getElementById("export").onclick = () => {
    let csv=[];
    document.querySelectorAll("table").forEach(t=>{
      t.querySelectorAll("tr").forEach(r=>{
        csv.push([...r.children].map(td=>'"'+td.innerText+'"').join(","));
      });
    });
    const blob=new Blob([csv.join("\\n")],{type:"text/csv"});
    const a=document.createElement("a");
    a.href=URL.createObjectURL(blob);
    a.download="corporate_actions.csv";
    a.click();
  };

});
</script>
"""

    return f"""
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Corporate Actions</title>{css}</head>
<body>
<div class="container">
<h1>Upcoming Corporate Actions</h1>

<input id="search" placeholder="Search company, symbol, action…">
<button id="export">📤 Export CSV</button>

{html_table(["Company","Type","Amount","Category","Ex-Date","Record Date"], div_rows, "Dividends")}
{html_table(["Company","Ratio","Ex-Date","Record Date"], bonus_rows, "Bonus Issues")}
{html_table(["Company","Action","From","To","Ex-Date","Record Date"], split_rows, "Splits & Others")}

<p><b>Green rows:</b> Ex-date within next 7 days</p>
</div>
{js}
</body>
</html>
"""

# ---------------- Main ----------------

def git_push():
    subprocess.run(["git", "add", "index.html", "corporate_actions.json"], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Auto update {date.today()}"],
        check=True
    )
    subprocess.run(["git", "push"], check=True)

def main():
    rows = load_csv(CSV_IN)
    data = build_json(rows)
    JSON_OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    HTML_OUT.write_text(build_index_html(data), encoding="utf-8")
    git_push()
    print("✅ index.html and corporate_actions.json generated")

if __name__ == "__main__":
    main()
   

