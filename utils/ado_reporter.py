"""
ADO Reporter — creates a work item in Azure DevOps for each failed E2E test case
and uploads all step attachments collected during execution.
"""
import base64
from typing import List, Optional, Tuple

try:
    import requests as _req
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class StepReport:
    """Collects attachment content for one test step alongside Allure reporting."""

    def __init__(self, label: str, index: int):
        self.label          = label
        self.index          = index
        self.attachments:   List[Tuple[str, str]] = []  # (name, content)
        self.failed         = False
        self.failure_reason = ""

    def add(self, name: str, content: str):
        self.attachments.append((name, content))


class ADOReporter:
    """
    Reports failed E2E test cases to Azure DevOps as work items.

    Work item title  : TC_ID  or  TC_ID - TC Name
    Tags             : E2E; <env_label>; <tc_id>
    Attachments      : every step's request, response, assertions, etc.
    """

    def __init__(
        self,
        org_url:        str,
        project:        str,
        pat:            str,
        work_item_type: str = "Bug",
    ):
        self.org_url        = org_url.rstrip("/")
        self.project        = project
        self.work_item_type = work_item_type
        token               = base64.b64encode(f":{pat}".encode()).decode()
        self._auth          = {"Authorization": f"Basic {token}"}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def report_failure(
        self,
        tc_id:     str,
        ado_title: str,
        env_label: str,
        steps:     List[StepReport],
    ) -> Optional[int]:
        """
        Create a work item for the failed test case and link all step attachments.
        Returns the work item ID, or None on error.  Never raises.
        """
        if not _AVAILABLE:
            print("ADO reporting skipped — 'requests' library not installed.")
            return None
        try:
            description = self._build_description(tc_id, env_label, steps)
            tags        = ";".join(t for t in ["E2E", env_label, tc_id] if t)

            wi_id = self._create_work_item(ado_title, description, tags)
            if wi_id is None:
                return None

            for step in steps:
                for name, content in step.attachments:
                    safe = f"{step.label}_{name}".replace(" ", "_").replace("/", "-")
                    url  = self._upload_attachment(content.encode("utf-8"), f"{safe}.txt")
                    if url:
                        self._link_attachment(wi_id, url, f"[{step.label}] {name}")

            print(f"ADO: work item #{wi_id} created for '{tc_id}'")
            return wi_id
        except Exception as exc:
            print(f"ADO reporting error for '{tc_id}': {exc}")
            return None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_description(
        self, tc_id: str, env_label: str, steps: List[StepReport]
    ) -> str:
        parts = [f"<b>Test Case:</b> {tc_id}"]
        if env_label:
            parts.append(f"<b>Environment:</b> {env_label}")
        parts.append("<br/>")
        for s in steps:
            icon = "&#10060;" if s.failed else "&#9989;"
            parts.append(f"{icon} <b>{s.label}</b>")
            if s.failure_reason:
                parts.append(f"<pre>{s.failure_reason}</pre>")
        return "<br/>".join(parts)

    def _create_work_item(
        self, title: str, description: str, tags: str
    ) -> Optional[int]:
        url  = (
            f"{self.org_url}/{self.project}/_apis/wit/workitems"
            f"/${self.work_item_type}?api-version=7.0"
        )
        body = [
            {"op": "add", "path": "/fields/System.Title",       "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": description},
            {"op": "add", "path": "/fields/System.Tags",        "value": tags},
        ]
        resp = _req.post(
            url, json=body,
            headers={**self._auth, "Content-Type": "application/json-patch+json"},
        )
        if resp.ok:
            return resp.json()["id"]
        print(f"ADO: create work item failed: {resp.status_code} {resp.text[:300]}")
        return None

    def _upload_attachment(self, data: bytes, filename: str) -> Optional[str]:
        url  = (
            f"{self.org_url}/{self.project}/_apis/wit/attachments"
            f"?fileName={filename}&api-version=7.0"
        )
        resp = _req.post(
            url, data=data,
            headers={**self._auth, "Content-Type": "application/octet-stream"},
        )
        if resp.ok:
            return resp.json()["url"]
        print(f"ADO: attachment upload failed for '{filename}': {resp.status_code}")
        return None

    def _link_attachment(self, wi_id: int, att_url: str, comment: str):
        url  = (
            f"{self.org_url}/{self.project}/_apis/wit/workitems"
            f"/{wi_id}?api-version=7.0"
        )
        body = [{
            "op":    "add",
            "path":  "/relations/-",
            "value": {
                "rel":        "AttachedFile",
                "url":        att_url,
                "attributes": {"comment": comment},
            },
        }]
        _req.patch(
            url, json=body,
            headers={**self._auth, "Content-Type": "application/json-patch+json"},
        )
