import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import requests

RAW_README_URL = "https://raw.githubusercontent.com/northwesternfintech/2027QuantInternships/main/README.md"
STATE_FILE = "seen_roles.json"

SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]

def fetch_readme() -> str:
    r = requests.get(RAW_README_URL, timeout=30)
    r.raise_for_status()
    return r.text

def parse_roles(readme: str) -> dict:
    roles = {}
    current_company = None

    for line in readme.splitlines():
        line = line.strip()

        # company headers like: ## Akuna Capital
        if line.startswith("## "):
            current_company = line[3:].strip()
            roles[current_company] = []
            continue

        # markdown links in table/list rows
        if current_company:
            urls = re.findall(r'\((https?://[^)]+)\)', line)
            if urls:
                label = re.sub(r'\|', ' ', line)
                label = re.sub(r'\[.*?\]', '', label)
                label = re.sub(r'\(https?://[^)]+\)', '', label).strip()

                for url in urls:
                    roles[current_company].append({
                        "label": label[:200],
                        "url": url
                    })

    return roles

def load_state() -> dict:
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text())
    return {}

def save_state(state: dict) -> None:
    Path(STATE_FILE).write_text(json.dumps(state, indent=2, sort_keys=True))

def diff_roles(old: dict, new: dict) -> list:
    old_set = {
        (company, item["label"], item["url"])
        for company, items in old.items()
        for item in items
    }

    added = []
    for company, items in new.items():
        for item in items:
            key = (company, item["label"], item["url"])
            if key not in old_set:
                added.append(key)

    return added

def send_email(new_items: list) -> None:
    lines = ["New internship applications/links detected:\n"]
    for company, label, url in new_items:
        lines.append(f"- {company}\n  {label}\n  {url}\n")

    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"{len(new_items)} new internship posting(s)"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def main():
    latest = parse_roles(fetch_readme())
    previous = load_state()

    if previous:
        new_items = diff_roles(previous, latest)
        if new_items:
            send_email(new_items)

    save_state(latest)

if __name__ == "__main__":
    main()