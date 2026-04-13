"""
Terminal Bench 2.0 leaderboard scraper.
Fetches per-task data for all 123 entries and writes:
  - bench/data/entries.json       — full leaderboard metadata
  - bench/data/tasks.csv          — per-task pass rates across all entries
  - bench/data/task_summary.csv   — aggregated difficulty per task
"""

import json
import re
import time
import csv
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

BASE = "https://www.tbench.ai"
LEADERBOARD_URL = f"{BASE}/leaderboard/terminal-bench/2.0"
OUT_DIR = Path(__file__).parent / "data"
DELAY = 0.3  # seconds between requests


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def extract_entries(html: str) -> list[dict[str, Any]]:
    idx = html.index("agentName")
    search_from = max(0, idx - 20000)
    chunk = html[search_from:idx + 100]
    match = re.search(r"\[(\{.*)", chunk, re.DOTALL)
    if not match:
        raise ValueError("Could not find entries JSON array")
    start_pos = search_from + match.start()
    chunk = html[start_pos:]

    depth = 0
    i = 0
    end = 0
    while i < len(chunk):
        c = chunk[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1

    raw = chunk[:end].replace('\\"', '"').replace("\\\\", "\\")
    return json.loads(raw)


def entry_url(entry: dict[str, Any]) -> str:
    agent = entry["agentName"]
    version = entry.get("agentVersion", "unknown")
    names = entry["modelNames"]
    providers = entry["modelProviders"]
    if len(names) == 1:
        model_str = f"{names[0]}@{providers[0]}"
    else:
        model_str = "multiple"
    return f"{LEADERBOARD_URL}/{urllib.parse.quote(agent, safe='')}/{urllib.parse.quote(version, safe='')}/{urllib.parse.quote(model_str, safe='')}"


def parse_tasks(html: str) -> list[dict[str, Any]]:
    """Parse per-task rows from a detail page."""
    rows = []
    # Each row: task name, trials, successes
    pattern = re.compile(
        r'<span class="font-normal">([^<]+)</span></td>'
        r'.*?<p class="text-right">(\d+)</p>'
        r'.*?<p class="text-right">(\d+)</p>',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        task = m.group(1).strip()
        trials = int(m.group(2))
        successes = int(m.group(3))
        rows.append({"task": task, "trials": trials, "successes": successes,
                     "rate": successes / trials if trials > 0 else 0.0})
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching leaderboard index…")
    html = fetch(LEADERBOARD_URL)
    entries = extract_entries(html)
    print(f"Found {len(entries)} entries")

    # Save raw entries
    (OUT_DIR / "entries.json").write_text(json.dumps(entries, indent=2))

    # Fetch each detail page
    all_results: list[dict[str, Any]] = []
    failed: list[str] = []

    for i, entry in enumerate(entries):
        url = entry_url(entry)
        label = f"{entry['agent']} / {entry['model']}"
        print(f"[{i+1:3}/{len(entries)}] {label} …", end=" ", flush=True)
        try:
            detail_html = fetch(url)
            tasks = parse_tasks(detail_html)
            if not tasks:
                print(f"WARNING: 0 tasks parsed")
                failed.append(url)
            else:
                print(f"{len(tasks)} tasks")
                for t in tasks:
                    all_results.append({
                        "rank": i + 1,
                        "agent": entry["agent"],
                        "agent_key": entry["agentName"],
                        "model": entry["model"],
                        "model_key": entry["modelNames"],
                        "org": entry["agentOrganization"],
                        "overall_accuracy": entry["accuracy"],
                        "task": t["task"],
                        "trials": t["trials"],
                        "successes": t["successes"],
                        "rate": t["rate"],
                    })
        except Exception as e:
            print(f"ERROR: {e}")
            failed.append(url)
        time.sleep(DELAY)

    print(f"\nFailed: {len(failed)}")
    if failed:
        for u in failed:
            print(" ", u)

    # Write flat task results
    task_csv = OUT_DIR / "tasks.csv"
    with task_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "rank", "agent", "agent_key", "model", "model_key",
            "org", "overall_accuracy", "task", "trials", "successes", "rate",
        ])
        writer.writeheader()
        for row in all_results:
            writer.writerow({**row,
                             "model": str(row["model"]),
                             "model_key": str(row["model_key"])})

    # Aggregate per-task difficulty
    task_stats: dict[str, dict[str, Any]] = {}
    for row in all_results:
        t = row["task"]
        if t not in task_stats:
            task_stats[t] = {"task": t, "total_trials": 0, "total_successes": 0,
                             "entries": 0, "sum_rate": 0.0}
        task_stats[t]["total_trials"] += row["trials"]
        task_stats[t]["total_successes"] += row["successes"]
        task_stats[t]["entries"] += 1
        task_stats[t]["sum_rate"] += row["rate"]

    for t in task_stats.values():
        t["avg_rate"] = t["sum_rate"] / t["entries"] if t["entries"] > 0 else 0.0
        t["global_rate"] = t["total_successes"] / t["total_trials"] if t["total_trials"] > 0 else 0.0

    summary = sorted(task_stats.values(), key=lambda x: x["avg_rate"])

    summary_csv = OUT_DIR / "task_summary.csv"
    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task", "avg_rate", "global_rate", "total_trials",
            "total_successes", "entries", "sum_rate",
        ])
        writer.writeheader()
        writer.writerows(summary)

    print(f"\nWrote {task_csv}")
    print(f"Wrote {summary_csv}")
    print(f"\nTop 10 EASIEST (highest avg pass rate):")
    for t in sorted(summary, key=lambda x: -x["avg_rate"])[:10]:
        print(f"  {t['task']:<45} {t['avg_rate']*100:5.1f}%")
    print(f"\nTop 10 HARDEST (lowest avg pass rate):")
    for t in summary[:10]:
        print(f"  {t['task']:<45} {t['avg_rate']*100:5.1f}%")


if __name__ == "__main__":
    main()
