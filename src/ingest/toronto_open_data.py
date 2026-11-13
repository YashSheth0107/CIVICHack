"""
Minimal client for the City of Toronto Open Data CKAN API.

Reference: https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/help_show
"""
from __future__ import annotations

import os
from typing import Any

import requests

from config import CKAN_BASE


def get_package(package_name: str) -> dict[str, Any]:
    """Fetch full package metadata (including the resource list) by its
    CKAN slug, e.g. 'members-of-toronto-city-council-voting-record'.
    """
    resp = requests.get(
        f"{CKAN_BASE}/api/3/action/package_show",
        params={"id": package_name},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN package_show failed for '{package_name}': {payload}")
    return payload["result"]


def list_resources(package_name: str) -> list[dict[str, Any]]:
    """Return the resource list ({name, format, url, id, ...}) for a package."""
    return get_package(package_name)["resources"]


def find_resource(package_name: str, *, filename_contains: str) -> dict[str, Any]:
    """Find the single resource whose download URL contains
    `filename_contains` (case-insensitive). Raises if zero or more than
    one match.

    Matches on the URL's filename, NOT the resource's 'name' field --
    the 'name' is an editable display label the publisher can (and, on
    this portal, has) change at any time, e.g. from a filename-shaped
    string to a human-readable one. The URL is generated from the
    actual uploaded file and has stayed stable across that change, so
    it's the reliable thing to match on.
    """
    needle = filename_contains.lower()
    matches = [r for r in list_resources(package_name) if needle in r["url"].lower()]
    if not matches:
        raise ValueError(f"No resource with a URL matching '{filename_contains}' in package '{package_name}'")
    if len(matches) > 1:
        urls = [m["url"] for m in matches]
        raise ValueError(f"Ambiguous match for '{filename_contains}': {urls}")
    return matches[0]


def download_resource(resource: dict[str, Any], dest_path: str) -> str:
    """Download a resource dict (from list_resources/find_resource) to dest_path."""
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    resp = requests.get(resource["url"], timeout=120)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)
    return dest_path
