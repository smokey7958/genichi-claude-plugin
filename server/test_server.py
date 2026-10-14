"""End-to-end check of the RFQ server over real streamable HTTP, with delivery to files.

    python test_server.py

Starts genichi_rfq_server.py on a local port with RFQ_DELIVERY=file, then uses the MCP
client to list tools, check the annotations, send one RFQ, and exercise the validation
and rate-limit errors. Nothing is emailed.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from email import message_from_bytes
from email.policy import default
from pathlib import Path

from mcp.client import Client

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/mcp"

SAMPLE = {
    "contact_name": "Test Buyer",
    "contact_email": "buyer@example.com",
    "company": "Example Robotics GmbH",
    "country": "Germany",
    "product_name": "Stainless steel mounting bracket",
    "description": "L-shaped bracket that holds a 2 kg sensor on an aluminium frame outdoors. "
    "Two M6 clearance holes on each leg, 90 degree bend, no sharp edges.",
    "quantity": "500 pcs; 2,000 pcs",
    "material": "SUS304, 3 mm sheet",
    "dimensions_and_tolerances": "60 x 40 x 30 mm, holes +/-0.1 mm, general ISO 2768-m",
    "finish_and_treatment": "Bead blasted, passivated",
    "needed_by": "2026-12-15",
    "drawing_links": ["https://example.com/bracket.pdf"],
}


async def check(outbox: Path) -> None:
    async with Client(URL) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == ["submit_rfq"], tools
        ann = tools[0].annotations.model_dump(by_alias=True, exclude_none=True)
        assert ann == {
            "title": "Send quote request to Genichi Tool",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }, ann
        print("tools/list ok, annotations:", ann)

        res = await client.call_tool("submit_rfq", SAMPLE)
        assert not res.is_error, res
        receipt = res.structured_content
        print("receipt:", receipt)
        eml = outbox / f"{receipt['reference']}.eml"
        msg = message_from_bytes(eml.read_bytes(), policy=default)
        assert msg["To"] == "service@genichi-tool.com"
        assert msg["Reply-To"] == "Test Buyer <buyer@example.com>"
        assert receipt["reference"] in msg["Subject"]
        body = msg.get_content()
        assert "SUS304" in body and "https://example.com/bracket.pdf" in body
        print("email ok:", msg["Subject"])

        bad = await client.call_tool("submit_rfq", dict(SAMPLE, contact_email="not-an-email"))
        assert bad.is_error and "contact_email" in bad.content[0].text, bad
        print("invalid email rejected:", bad.content[0].text)

        bad = await client.call_tool("submit_rfq", dict(SAMPLE, drawing_links=["http://insecure.example.com/x"]))
        assert bad.is_error and "https" in bad.content[0].text, bad
        print("non-https link rejected")

        short = await client.call_tool("submit_rfq", dict(SAMPLE, description="too short"))
        assert short.is_error, short
        print("short description rejected")

        results = [await client.call_tool("submit_rfq", SAMPLE) for _ in range(4)]
        assert any(r.is_error and "Too many requests" in r.content[0].text for r in results), results
        print("rate limit ok after", sum(not r.is_error for r in results) + 1, "sends for one address")


def call_raw(args: dict, forwarded_for: str) -> dict:
    """tools/call over plain HTTP, with the X-Forwarded-For header a hosting router adds."""
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "submit_rfq", "arguments": args}}
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Forwarded-For": forwarded_for,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["result"]


def check_ip_limit() -> None:
    # All claude.ai users arrive from Anthropic's range, so the per-IP limit skips it; other addresses keep it.
    shared = [call_raw(dict(SAMPLE, contact_email=f"claude{i}@example.com"), "160.79.104.10") for i in range(7)]
    assert not any(r["isError"] for r in shared), shared
    other = [call_raw(dict(SAMPLE, contact_email=f"direct{i}@example.com"), "198.51.100.7") for i in range(6)]
    assert [r["isError"] for r in other] == [False] * 5 + [True], other  # RFQ_MAX_PER_IP_HOUR defaults to 5
    print("per-IP limit skips Anthropic's range and still applies to other addresses")


def main() -> None:
    outbox = Path(tempfile.mkdtemp(prefix="rfq-outbox-"))
    env = dict(os.environ, RFQ_DELIVERY="file", RFQ_OUTBOX=str(outbox), PORT=str(PORT), RFQ_ALLOWED_HOSTS="")
    proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("genichi_rfq_server.py"))], env=env)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        asyncio.run(check(outbox))
        check_ip_limit()
        print("ALL CHECKS PASSED")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(outbox, ignore_errors=True)


if __name__ == "__main__":
    main()
