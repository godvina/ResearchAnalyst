"""Shared API client for the Research Analyst Platform frontend."""

import os
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1",
)

_session = requests.Session()
_retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504],
               allowed_methods=["GET", "POST", "DELETE", "PATCH"])
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))

TIMEOUT = 30


class APIError(Exception):
    def __init__(self, status_code: int, detail: str, request_id: str = ""):
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id
        super().__init__(f"[{status_code}] {detail}")


def _url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}{path}"


def _handle(resp: requests.Response) -> dict:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.ok:
        return body
    detail = body.get("error", {}).get("message", resp.text) if isinstance(body.get("error"), dict) else resp.text
    raise APIError(resp.status_code, detail, body.get("requestId", ""))


def create_case_file(topic_name: str, description: str, parent_case_id: Optional[str] = None) -> dict:
    payload: dict[str, Any] = {"topic_name": topic_name, "description": description}
    if parent_case_id:
        payload["parent_case_id"] = parent_case_id
    return _handle(_session.post(_url("/case-files"), json=payload, timeout=TIMEOUT))


def list_case_files(**kwargs) -> dict:
    params = {k: v for k, v in kwargs.items() if v is not None}
    return _handle(_session.get(_url("/case-files"), params=params, timeout=TIMEOUT))


def get_case_file(case_id: str) -> dict:
    return _handle(_session.get(_url(f"/case-files/{case_id}"), timeout=TIMEOUT))


def delete_case_file(case_id: str) -> dict:
    return _handle(_session.delete(_url(f"/case-files/{case_id}"), timeout=TIMEOUT))


def archive_case_file(case_id: str) -> dict:
    return _handle(_session.post(_url(f"/case-files/{case_id}/archive"), timeout=TIMEOUT))


def ingest_documents(case_id: str, files: list[dict]) -> dict:
    return _handle(_session.post(_url(f"/case-files/{case_id}/ingest"), json={"files": files}, timeout=TIMEOUT))


def discover_patterns(case_id: str) -> dict:
    return _handle(_session.post(_url(f"/case-files/{case_id}/patterns"), timeout=TIMEOUT))


def get_neighbors(case_id: str, entity_name: str) -> dict:
    return _handle(_session.post(_url(f"/case-files/{case_id}/patterns"),
                                 json={"entity_name": entity_name}, timeout=TIMEOUT))


def get_patterns(case_id: str) -> dict:
    return _handle(_session.get(_url(f"/case-files/{case_id}/patterns"), timeout=TIMEOUT))


def search(case_id: str, query: str, top_k: int = 10) -> dict:
    return _handle(_session.post(_url(f"/case-files/{case_id}/search"), json={"query": query, "top_k": top_k}, timeout=TIMEOUT))


def drill_down(case_id: str, topic_name: str, description: str,
               entity_names: Optional[list[str]] = None, pattern_id: Optional[str] = None) -> dict:
    payload: dict[str, Any] = {"topic_name": topic_name, "description": description}
    if entity_names:
        payload["entity_names"] = entity_names
    if pattern_id:
        payload["pattern_id"] = pattern_id
    return _handle(_session.post(_url(f"/case-files/{case_id}/drill-down"), json=payload, timeout=TIMEOUT))


def analyze_cross_case(case_ids: list[str]) -> dict:
    return _handle(_session.post(_url("/cross-case/analyze"), json={"case_ids": case_ids}, timeout=TIMEOUT))


def create_cross_case_graph(name: str, case_ids: list[str]) -> dict:
    return _handle(_session.post(_url("/cross-case/graphs"), json={"name": name, "case_ids": case_ids}, timeout=TIMEOUT))


def update_cross_case_graph(graph_id: str, add_case_ids: Optional[list[str]] = None,
                            remove_case_ids: Optional[list[str]] = None) -> dict:
    payload: dict[str, Any] = {}
    if add_case_ids:
        payload["add_case_ids"] = add_case_ids
    if remove_case_ids:
        payload["remove_case_ids"] = remove_case_ids
    return _handle(_session.patch(_url(f"/cross-case/graphs/{graph_id}"), json=payload, timeout=TIMEOUT))


def get_cross_case_graph(graph_id: str) -> dict:
    return _handle(_session.get(_url(f"/cross-case/graphs/{graph_id}"), timeout=TIMEOUT))


# === Organization / Matter / Collection endpoints ===

def list_organizations() -> dict:
    return _handle(_session.get(_url("/organizations"), timeout=TIMEOUT))


def get_organization(org_id: str) -> dict:
    return _handle(_session.get(_url(f"/organizations/{org_id}"), timeout=TIMEOUT))


def list_matters(org_id: str, status: Optional[str] = None) -> dict:
    params: dict[str, Any] = {}
    if status:
        params["status"] = status
    return _handle(_session.get(_url(f"/organizations/{org_id}/matters"), params=params, timeout=TIMEOUT))


def get_matter(matter_id: str, org_id: str) -> dict:
    return _handle(_session.get(_url(f"/matters/{matter_id}"), params={"org_id": org_id}, timeout=TIMEOUT))


def list_collections(matter_id: str, org_id: str) -> dict:
    return _handle(_session.get(_url(f"/matters/{matter_id}/collections"), params={"org_id": org_id}, timeout=TIMEOUT))


def get_collection(matter_id: str, collection_id: str, org_id: str) -> dict:
    return _handle(_session.get(_url(f"/matters/{matter_id}/collections/{collection_id}"), params={"org_id": org_id}, timeout=TIMEOUT))


def promote_collection(matter_id: str, collection_id: str, org_id: str) -> dict:
    return _handle(_session.post(_url(f"/matters/{matter_id}/collections/{collection_id}/promote"), params={"org_id": org_id}, timeout=TIMEOUT))


def reject_collection(matter_id: str, collection_id: str, org_id: str) -> dict:
    return _handle(_session.post(_url(f"/matters/{matter_id}/collections/{collection_id}/reject"), params={"org_id": org_id}, timeout=TIMEOUT))
