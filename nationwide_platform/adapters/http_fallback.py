import subprocess
from dataclasses import dataclass
from typing import Dict, Optional

import requests


@dataclass
class CurlFallbackResponse:
    url: str
    status_code: int
    text: str
    headers: Dict[str, str]

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8", errors="ignore")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for {self.url}")


def curl_get(
    url: str,
    timeout: int,
    user_agent: str,
    referer: Optional[str] = None,
) -> Optional[CurlFallbackResponse]:
    command = [
        "curl",
        "-L",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout),
        "-A",
        user_agent,
    ]
    if referer:
        command.extend(["-e", referer])
    command.extend(
        [
            "-w",
            "\n__CURL_STATUS__:%{http_code}",
            "--url",
            url,
        ]
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        return None

    body, marker, status_part = completed.stdout.rpartition("\n__CURL_STATUS__:")
    if not marker:
        return None

    try:
        status_code = int(status_part.strip() or "0")
    except ValueError:
        return None

    return CurlFallbackResponse(
        url=url,
        status_code=status_code,
        text=body,
        headers={},
    )
