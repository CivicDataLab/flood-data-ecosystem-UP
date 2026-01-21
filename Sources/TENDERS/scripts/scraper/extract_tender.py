# extract_tender.py
import os
import re
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import pandas as pd


def _norm(text: str) -> str:
    if text is None:
        return ""
    t = text.replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _safe_col(name: str) -> str:
    name = _norm(name)
    name = re.sub(r"[:/\\\[\]\(\)\*\?,]+", " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name



def _iter_sections_and_tables(soup):

    from bs4 import BeautifulSoup
    trs = soup.find_all("tr")
    idxs = [i for i, tr in enumerate(trs) if tr.find("td", class_="section_head")]
    seen = set()

    for pos, i in enumerate(idxs):
        head_td = trs[i].find("td", class_="section_head")
        title = head_td.get_text(strip=True) if head_td else ""
        tables = []

        # 1) the real parent table that holds this section (critical for Work /Item(s))
        parent_tbl = head_td.find_parent("table")
        if parent_tbl and id(parent_tbl) not in seen:
            tables.append(parent_tbl); seen.add(id(parent_tbl))

        # 2) tables in the rows until the next section head (keeps “KV before grid” cases)
        j = idxs[pos + 1] if pos + 1 < len(idxs) else len(trs)
        frag_html = "<table>" + "".join(str(r) for r in trs[i + 1 : j]) + "</table>"
        frag = BeautifulSoup(frag_html, "lxml")
        for t in frag.find_all("table"):
            if id(t) not in seen:
                tables.append(t); seen.add(id(t))

        yield title, tables


def _kv_from_vertical_table(tbl):

    kv = {}
    for tr in tbl.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) != 2:
            continue
        k = _safe_col(_norm(tds[0].get_text()).rstrip(":"))
        v = _norm(tds[1].get_text())
        if not k:
            continue
        base, i, key = k, 1, k
        while key in kv:
            i += 1
            key = f"{base}__{i}"
        kv[key] = v
    return kv
def _tkey(title: str) -> str:
    t = _norm(title).lower()
    return re.sub(r"\s+", " ", t).strip()

def _is_bids_list(title: str) -> bool:
    t = _tkey(title)
    return "bids list" in t and "awarded" not in t

def _is_fin_eval(title: str) -> bool:
    t = _tkey(title)
    return ("financial evaluation bid list" in t
            or "finance evaluation bid list" in t
            or "financial bid opening summary" in t
            or "finance bid opening summary" in t)

def _is_awarded(title: str) -> bool:
    t = _tkey(title)
    return any(k in t for k in [
        "awarded bids list", "awarded bid list",
        "award of contract", "aoc/bid details",
        "aoc details", "aoc list", "aoc"
    ])

def _flatten_pairs_table(tbl):
    """
    For rows like [k1, v1, k2, v2, (...)] produce:
      k1__rowN = v1
      k2__rowN = v2
    Works well for 'Critical Dates' blocks.
    """
    d, rowno = {}, 0
    for tr in tbl.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if len(cells) >= 4 and len(cells) % 2 == 0:
            rowno += 1
            for j in range(0, len(cells), 2):
                k = _safe_col(cells[j])
                v = _norm(cells[j + 1])
                key = f"{k}__row{rowno}"
                d[key] = v
    return d

def _tkey(title: str) -> str:
    """Normalize a section title for matching."""
    t = _norm(title).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _is_bids_list(title: str) -> bool:
    t = _tkey(title)
    return "bids list" in t and "awarded" not in t  # plain "Bids List"

def _is_fin_eval(title: str) -> bool:
    t = _tkey(title)
    return (
        "financial evaluation bid list" in t
        or "finance evaluation bid list" in t
        or "financial bid opening summary" in t
        or "finance bid opening summary" in t
    )

def _is_awarded(title: str) -> bool:
    """Covers Awarded Bids List + common AOC/Award variants across portals."""
    t = _tkey(title)
    return any(
        key in t
        for key in [
            "awarded bids list",
            "awarded bid list",
            "award of contract",
            "aoc/bid details",
            "aoc details",
            "aoc list",
            "aoc",  # keep broad last
        ]
    )


from collections import Counter

def _flatten_horizontal_table(tbl, row_suffix: str = "row"):
    """
    Flatten grid into Header__<row_suffix>N -> value.
    Robust to leading 1-cell title rows.
    """
    d = {}
    rows = tbl.find_all("tr")
    if not rows:
        return d

    counts = [len(tr.find_all(["th","td"])) for tr in rows if len(tr.find_all(["th","td"])) >= 2]
    if not counts:
        return d
    target = Counter(counts).most_common(1)[0][0]

    header_idx, headers = None, []
    for i, tr in enumerate(rows):
        cells = tr.find_all(["th","td"])
        if len(cells) == target:
            headers = [_safe_col(_norm(c.get_text())) for c in cells]
            header_idx = i
            break
    if header_idx is None:
        return d

    for r_idx, tr in enumerate(rows[header_idx + 1:], start=1):
        cells = tr.find_all("td")
        if len(cells) != target:
            continue
        for h, td in zip(headers, cells):
            key = f"{h}__{row_suffix}{r_idx}"
            d[key] = _norm(td.get_text())
    return d


def _flatten_mixed_kv_pairs_table(tbl):

    d = {}
    rowno_pairs = 0
    for tr in tbl.find_all("tr"):
        cells = tr.find_all("td")
        n = len(cells)
        if n == 2:
            k = _safe_col(_norm(cells[0].get_text()).rstrip(":"))
            v = _norm(cells[1].get_text())
            if not k:
                continue
            base, i, key = k, 1, k
            while key in d:
                i += 1; key = f"{base}__{i}"
            d[key] = v
        elif n >= 4 and n % 2 == 0:
            rowno_pairs += 1
            for j in range(0, n, 2):
                k = _safe_col(_norm(cells[j].get_text()).rstrip(":"))
                v = _norm(cells[j + 1].get_text())
                if not k:
                    continue
                d[f"{k}__row{rowno_pairs}"] = v
    return d


def _merge_into(base: dict, add: dict):
    """
    Merge add -> base:
      - If key not present -> set
      - If present and base[key] empty -> overwrite
      - If present and equal -> skip
      - If present and both non-empty & different -> create key__2, __3...
    """
    for k, v in add.items():
        if k not in base:
            base[k] = v
            continue

        if (base[k] is None or base[k] == "") and v:
            base[k] = v
            continue

        if base[k] == v:
            continue

        i = 2
        nk = f"{k}__{i}"
        while nk in base and base[nk] != v:
            i += 1
            nk = f"{k}__{i}"
        base[nk] = v





def parse_summary_to_row(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    row = {}

    for title, tables in _iter_sections_and_tables(soup):
        for tbl in tables:
            rows = tbl.find_all("tr")
            if not rows:
                continue

            tds_per_row = [len(tr.find_all("td")) for tr in rows]
            two_col_major = sum(c == 2 for c in tds_per_row) >= max(2, int(0.6 * len(rows)))

            if _is_bids_list(title) or _is_fin_eval(title) or _is_awarded(title):
                if two_col_major:
                    kv = _kv_from_vertical_table(tbl)                     # KV before grid
                else:
                    # key change: awarded rows use a unique row suffix
                    kv = _flatten_horizontal_table(
                        tbl,
                        row_suffix=("awarded_row" if _is_awarded(title) else "row")
                    )
            else:
                kv = _kv_from_vertical_table(tbl) if two_col_major else {}

            _merge_into(row, kv)

    return row



def parse_view_to_row(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    row = {}

    for title, tables in _iter_sections_and_tables(soup):
        tlow = title.lower()
        keep = (
            title == "Basic Details"
            or tlow.startswith("work")                      # Work /Item(s)
            or tlow.startswith("critical dates")
            or ("payment" in tlow and ("instrument" in tlow or "instruction" in tlow))
            or title.startswith("Cover Details")
            or title == "Latest Corrigendum List"
            or title.startswith("Other")
            or _is_awarded(title)                           # <-- NEW: capture Awarded/AOC if present here
        )
        if not keep:
            continue

        for tbl in tables:
            rows = tbl.find_all("tr")
            if not rows:
                continue

            if tlow.startswith("work"):
                kv = _flatten_mixed_kv_pairs_table(tbl)
            else:
                td_counts = [len(tr.find_all("td")) for tr in rows]
                two_col_major = sum(c == 2 for c in td_counts) >= max(2, int(0.6 * len(rows)))
                even_ge4_majority = sum((c >= 4 and c % 2 == 0) for c in td_counts) >= max(1, int(0.5 * len(rows)))

                if title == "Critical Dates" or even_ge4_majority:
                    kv = _flatten_pairs_table(tbl)
                elif two_col_major:
                    kv = _kv_from_vertical_table(tbl)
                else:
                    kv = _flatten_horizontal_table(tbl)

            _merge_into(row, kv)

    return row


def _merge_rows(*rows: dict) -> dict:
    """Merge dicts using _merge_into rules."""
    out = {}
    for r in rows:
        _merge_into(out, r)
    return out

def process_one_tender(summary_html_path: str, view_html_path: str, out_dir: str):
    """
    Parse one tender (summary + view), merge to a one-row CSV:
      final_<tender_id>.csv
    """
    tid = Path(summary_html_path).stem
    if tid.endswith("_summary"):
        tid = tid[:-len("_summary")]

    with open(summary_html_path, "r", encoding="utf-8") as f:
        s_html = f.read()
    with open(view_html_path, "r", encoding="utf-8") as f:
        v_html = f.read()

    summary_row = parse_summary_to_row(s_html)
    view_row    = parse_view_to_row(v_html)
    final_row   = _merge_rows(summary_row, view_row)

    # Optional: float tender-id-like fields to front
    preferred = [c for c in final_row.keys() if c.lower().startswith("tender_id")]
    cols = preferred + [c for c in final_row.keys() if c not in preferred]

    df = pd.DataFrame([{c: final_row.get(c, "") for c in cols}])
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"final_{Path(tid).name}.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    #print(f"Wrote {out_csv}")





def _iter_tender_pairs(root_dir: str):
    """
    Yield (summary_path, view_path) for every pair under root_dir.
    Pair = <tender>_summary.html and <tender>_view_details.html in same folder.
    """
    for dirpath, _, filenames in os.walk(root_dir):
        files_set = set(filenames)
        for fname in filenames:
            if not fname.endswith("_summary.html"):
                continue
            base = fname[:-len("_summary.html")]
            view_name = base + "_view_details.html"
            if view_name in files_set:
                yield os.path.join(dirpath, fname), os.path.join(dirpath, view_name)
            else:
                print(f"Missing view_details for: {os.path.join(dirpath, fname)}")

def process_tree(root_dir: str, out_dir: str, workers: int = 0, skip_existing: bool = True):
    """
    Walk root_dir, find all summary/view pairs, and process each.
    If workers > 1, uses ThreadPoolExecutor for parallelism.
    """
    os.makedirs(out_dir, exist_ok=True)
    pairs = list(_iter_tender_pairs(root_dir))
    if not pairs:
        print(f"[!] No pairs found under: {root_dir}")
        return

    print(f"Found {len(pairs)} tender pairs under {root_dir}")

    def _do(pair):
        summary_path, view_path = pair
        tid = Path(summary_path).stem
        if tid.endswith("_summary"):
            tid = tid[:-len("_summary")]
        out_csv = os.path.join(out_dir, f"final_{Path(tid).name}.csv")
        if skip_existing and os.path.exists(out_csv):
            return f"Skipped (exists): {out_csv}"
        process_one_tender(summary_path, view_path, out_dir)
        return #f"Done: {out_csv}"

    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=16) as ex:
            futures = [ex.submit(_do, p) for p in pairs]
            for fut in as_completed(futures):
                print(fut.result())
    else:
        for p in pairs:
            print(_do(p))



if __name__ == "__main__":

    ROOT_DIR = r"D:\CDL\saved-html\2024\january-june"              
    OUT_DIR  = r"D:\CDL\saved-html\2025\extracted_tables\2024\january-june"  


    process_tree(ROOT_DIR, OUT_DIR, workers=16, skip_existing=True)




