#!/usr/bin/env python3
"""Hetzner Server Auction watcher.

Polls Hetzner's public live_data JSON and notifies via ntfy.sh / Discord
when a new server matches user filters (CPU/RAM/disks/price/datacenter).

Run as cron job (one-shot) or daemon (loop with --daemon).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import click
import requests
import yaml

HETZNER_API_URL = (
    "https://www.hetzner.com/_resources/app/data/app/live_data_sb_EUR.json"
)
DEFAULT_CONFIG = Path("config.yaml")
DEFAULT_STATE = Path(".state.json")
USER_AGENT = "hetzner-auction-watch/1.0 (+https://github.com/DonaldSe/hetzner-auction-watch)"

log = logging.getLogger("hetzner-watch")


@dataclass(frozen=True)
class Filter:
    name: str
    ram_min_gb: int
    price_max_eur: float
    cpu_regex: re.Pattern[str]
    disk_type: str  # "nvme" | "ssd" | "any"
    disk_count_min: int
    disk_total_gb_min: int  # 0 = no constraint
    datacenters: list[str]  # ["FSN", "HEL", "NBG"] — substring match
    ecc_required: bool


def load_filters(cfg_path: Path) -> list[Filter]:
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    out: list[Filter] = []
    for f in raw.get("filters", []):
        out.append(
            Filter(
                name=f["name"],
                ram_min_gb=int(f.get("ram_min_gb", 64)),
                price_max_eur=float(f.get("price_max_eur", 50)),
                cpu_regex=re.compile(f.get("cpu_regex", ".*"), re.IGNORECASE),
                disk_type=f.get("disk_type", "nvme").lower(),
                disk_count_min=int(f.get("disk_count_min", 2)),
                disk_total_gb_min=int(f.get("disk_total_gb_min", 0)),
                datacenters=[s.upper() for s in f.get("datacenters", [])],
                ecc_required=bool(f.get("ecc_required", False)),
            )
        )
    return out


def fetch_servers() -> list[dict[str, Any]]:
    resp = requests.get(
        HETZNER_API_URL, headers={"User-Agent": USER_AGENT}, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("server", [])


def match(server: dict[str, Any], f: Filter) -> bool:
    if int(server.get("ram_size") or 0) < f.ram_min_gb:
        return False
    if float(server.get("price") or 1e9) > f.price_max_eur:
        return False
    if not f.cpu_regex.search(str(server.get("cpu", ""))):
        return False
    disk_data: dict[str, Any] = server.get("serverDiskData") or {}
    nvme_count = len(disk_data.get("nvme") or [])
    sata_count = len(disk_data.get("sata") or [])
    hdd_count = len(disk_data.get("hdd") or [])
    total_disks = nvme_count + sata_count + hdd_count
    if total_disks == 0:
        total_disks = len(server.get("hdd_arr") or [])
    if f.disk_type == "nvme":
        if nvme_count < f.disk_count_min:
            return False
    elif f.disk_type == "ssd":
        if (nvme_count + sata_count) < f.disk_count_min:
            return False
    elif total_disks < f.disk_count_min:
        return False
    if f.disk_total_gb_min > 0:
        nvme_gb = sum(disk_data.get("nvme") or [])
        sata_gb = sum(disk_data.get("sata") or [])
        hdd_gb = sum(disk_data.get("hdd") or [])
        if f.disk_type == "nvme":
            total_gb = nvme_gb
        elif f.disk_type == "ssd":
            total_gb = nvme_gb + sata_gb
        else:
            total_gb = nvme_gb + sata_gb + hdd_gb
        if total_gb < f.disk_total_gb_min:
            return False
    if f.datacenters:
        dc = str(server.get("datacenter", "")).upper()
        if not any(needle in dc for needle in f.datacenters):
            return False
    if f.ecc_required and not server.get("is_ecc"):
        return False
    return True


def server_id(server: dict[str, Any]) -> str:
    return str(server.get("key") or server.get("id") or "")


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: Path, ids: Iterable[str]) -> None:
    path.write_text(json.dumps(sorted(ids)), encoding="utf-8")


def format_message(server: dict[str, Any], filter_name: str) -> tuple[str, str]:
    name = server.get("name", "?")
    cpu = server.get("cpu", "?")
    ram = server.get("ram_size", "?")
    price = server.get("price", "?")
    disks = ", ".join(server.get("hdd_arr") or [])
    dc = server.get("datacenter", "?")
    bench = server.get("cpu_benchmark", "?")
    ecc = " ECC" if server.get("is_ecc") else ""
    sid = server_id(server)

    search_q = urllib.parse.quote(str(cpu))
    title = f"[{filter_name}] {cpu} @ {price}EUR/m"
    body = (
        f"{cpu}{ecc} ({bench} bench)\n"
        f"RAM: {ram} GB\n"
        f"Disks: {disks}\n"
        f"DC: {dc} | Price: {price}EUR/m | id={sid}\n"
        f"https://www.hetzner.com/sb#search={search_q}"
    )
    return title, body


def notify_ntfy(topic: str, title: str, body: str) -> None:
    base = os.getenv("NTFY_URL", "https://ntfy.sh")
    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "high",
        "Tags": "money,bell",
        "Click": _extract_url(body),
    }
    auth = os.getenv("NTFY_TOKEN")
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    resp = requests.post(
        f"{base}/{topic}",
        data=body.encode("utf-8"),
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()


def notify_discord(webhook: str, title: str, body: str) -> None:
    payload = {
        "embeds": [
            {
                "title": title,
                "description": body,
                "color": 0x00FF88,
                "url": _extract_url(body),
            }
        ]
    }
    resp = requests.post(webhook, json=payload, timeout=10)
    resp.raise_for_status()


def _extract_url(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("http"):
            return line
    return "https://www.hetzner.com/sb"


def run_once(cfg_path: Path, state_path: Path) -> int:
    filters = load_filters(cfg_path)
    if not filters:
        log.warning("No filters in %s; nothing to do.", cfg_path)
        return 0

    servers = fetch_servers()
    log.info("Fetched %d servers from Hetzner.", len(servers))

    seen = load_state(state_path)
    new_seen = set(seen)
    notifications = 0

    ntfy_topic = os.getenv("NTFY_TOPIC")
    discord_webhook = os.getenv("DISCORD_WEBHOOK")

    for srv in servers:
        sid = server_id(srv)
        if not sid:
            continue
        for f in filters:
            if not match(srv, f):
                continue
            dedup_key = f"{f.name}:{sid}"
            if dedup_key in seen:
                continue
            title, body = format_message(srv, f.name)
            log.info("MATCH %s", title)
            try:
                if ntfy_topic:
                    notify_ntfy(ntfy_topic, title, body)
                if discord_webhook:
                    notify_discord(discord_webhook, title, body)
                if not ntfy_topic and not discord_webhook:
                    print(f"=== MATCH ===\n{title}\n{body}\n", flush=True)
                new_seen.add(dedup_key)
                notifications += 1
            except requests.RequestException as exc:
                log.error("Notification failed for %s: %s", title, exc)

    save_state(state_path, new_seen)
    log.info("Cycle done. %d new notifications.", notifications)
    return notifications


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=DEFAULT_CONFIG,
    show_default=True,
)
@click.option(
    "--state",
    "state_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DEFAULT_STATE,
    show_default=True,
)
@click.option("--daemon", is_flag=True, help="Loop forever (cron-friendly default = off).")
@click.option("--interval", type=int, default=900, help="Daemon sleep seconds.")
@click.option("--verbose", "-v", is_flag=True)
def main(
    config_path: Path,
    state_path: Path,
    daemon: bool,
    interval: int,
    verbose: bool,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if daemon:
        log.info("Daemon mode, interval=%ds", interval)
        while True:
            try:
                run_once(config_path, state_path)
            except Exception:
                log.exception("Cycle crashed; will retry after interval.")
            time.sleep(interval)
    else:
        run_once(config_path, state_path)


if __name__ == "__main__":
    main()
