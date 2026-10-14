"""Genichi Tool RFQ intake: a remote MCP server with one tool, `submit_rfq`.

`submit_rfq` emails a customer's request for quotation (RFQ) for a custom-manufactured
product or part to Genichi Tool Co., Ltd. (service@genichi-tool.com). It is the backend
of the `genichi-custom-manufacturing` Claude plugin.

What the server sends and keeps
- It sends only the fields passed to `submit_rfq`, as one email to RFQ_TO
  (default service@genichi-tool.com). Reply-To is the customer's email, so Genichi
  staff answer the customer directly.
- It never emails anyone else. There is deliberately no auto-reply to the customer:
  that would let anyone use this server to send mail to arbitrary addresses.
- It logs only the reference number, time and delivery result, never the RFQ
  content or contact details.

Run locally (writes .eml files to ./outbox instead of sending):
    RFQ_DELIVERY=file python genichi_rfq_server.py

Environment
    PORT                        HTTP port (Heroku sets it)                      default 8000
    RFQ_DELIVERY                smtp | webhook | file                           default file
    RFQ_TO                      recipient                                       default service@genichi-tool.com
    RFQ_FROM                    From header; must be an address the SMTP login may send as
                                                                                default "Genichi RFQ <service@genichi-tool.com>"
    RFQ_SMTP_HOST / RFQ_SMTP_PORT / RFQ_SMTP_USER / RFQ_SMTP_PASSWORD
    RFQ_SMTP_SSL                1 = implicit TLS (port 465); otherwise STARTTLS  default 1
    RFQ_WEBHOOK_URL / RFQ_WEBHOOK_SECRET   webhook: POST the RFQ as JSON, secret in X-Genichi-Secret
    RFQ_ALLOWED_HOSTS           comma-separated Host headers to accept; empty turns host checking off
    RFQ_MAX_PER_EMAIL_HOUR      submissions per contact email per hour          default 3
    RFQ_MAX_PER_IP_HOUR         submissions per client IP per hour              default 5
    RFQ_SHARED_IPS              networks the per-IP limit skips, comma-separated
                                (claude.ai connector calls all come from Anthropic's outbound range)
                                                                                default 160.79.104.0/21
    RFQ_MAX_PER_DAY             submissions per day in total                    default 100
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets
import smtplib
import ssl
import time
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Annotated

import anyio
import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse

log = logging.getLogger("genichi-rfq")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RFQ_TO = os.environ.get("RFQ_TO", "service@genichi-tool.com")
DELIVERY = os.environ.get("RFQ_DELIVERY", "file").lower()
OUTBOX = Path(os.environ.get("RFQ_OUTBOX", Path(__file__).with_name("outbox")))
MAX_PER_EMAIL_HOUR = int(os.environ.get("RFQ_MAX_PER_EMAIL_HOUR", "3"))
MAX_PER_IP_HOUR = int(os.environ.get("RFQ_MAX_PER_IP_HOUR", "5"))
MAX_PER_DAY = int(os.environ.get("RFQ_MAX_PER_DAY", "100"))
# claude.ai calls connectors from Anthropic's outbound range (https://platform.claude.com/docs/en/api/ip-addresses),
# so every claude.ai user shares those addresses and a per-IP limit there would be one limit for all of them.
SHARED_NETWORKS = [
    ipaddress.ip_network(n.strip()) for n in os.environ.get("RFQ_SHARED_IPS", "160.79.104.0/21").split(",") if n.strip()
]
REPO_URL = "https://github.com/smokey7958/genichi-claude-plugin"

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")

server = MCPServer(
    name="genichi-rfq",
    title="Genichi Tool RFQ",
    description="Send requests for quotation for custom-manufactured products to Genichi Tool Co., Ltd.",
    website_url=REPO_URL,
    version="1.0.0",
    instructions=(
        "submit_rfq sends an email to Genichi Tool Co., Ltd. (service@genichi-tool.com). "
        "Call it only after the user has seen the final request and agreed to send it."
    ),
)


class RFQReceipt(BaseModel):
    reference: str = Field(description="Reference number to quote in any follow-up with Genichi Tool")
    sent_to: str = Field(description="Where the request was delivered")
    reply_to: str = Field(description="Address Genichi Tool will reply to")
    next_steps: str


# ---------------------------------------------------------------- rate limiting (in memory, per process)
_hits: dict[str, deque[float]] = defaultdict(deque)


def _allow(key: str, limit: int, window: float) -> bool:
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _client_ip(ctx: Context | None) -> str:
    """The last X-Forwarded-For entry is the one the hosting router added; earlier ones are client-supplied."""
    headers = (ctx.headers if ctx else None) or {}
    forwarded = headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() or "unknown"


def _shared_ip(ip: str) -> bool:
    try:
        return any(ipaddress.ip_address(ip) in net for net in SHARED_NETWORKS)
    except ValueError:  # "unknown"
        return False


# ---------------------------------------------------------------- email
def _one_line(text: str | None, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def _build_email(ref: str, fields: dict[str, object]) -> EmailMessage:
    order = [
        ("Product / part", "product_name"),
        ("Quantity", "quantity"),
        ("Description", "description"),
        ("Material", "material"),
        ("Dimensions & tolerances", "dimensions_and_tolerances"),
        ("Finish & treatment", "finish_and_treatment"),
        ("Target unit price", "target_unit_price"),
        ("Needed by", "needed_by"),
        ("Drawing / file links", "drawing_links"),
        ("Notes", "notes"),
    ]
    contact = [
        ("Name", "contact_name"),
        ("Company", "company"),
        ("Email", "contact_email"),
        ("Phone", "phone"),
        ("Country", "country"),
    ]

    def block(rows: list[tuple[str, str]]) -> str:
        """Short values one per line; lists and long text as their own paragraph."""
        out = []
        for label, key in rows:
            value = fields.get(key)
            if not value:
                continue
            is_list = isinstance(value, list)
            if is_list:
                value = "\n".join(f"  - {v}" for v in value)
            if is_list or "\n" in str(value) or len(str(value)) > 70:
                out.append(f"\n{label}:\n{value}\n")
            else:
                out.append(f"{label}: {value}")
        return "\n".join(out).strip()

    body = (
        f"New request for quotation {ref}\n"
        f"Received {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC through the Genichi Custom Manufacturing plugin for Claude.\n"
        f"Reply to this email to answer the customer directly.\n\n"
        f"== Customer ==\n{block(contact)}\n\n"
        f"== Request ==\n{block(order)}\n"
    )
    msg = EmailMessage()
    who = _one_line(str(fields.get("company") or fields.get("contact_name")), 60)
    msg["Subject"] = f"[{ref}] RFQ: {_one_line(str(fields['product_name']), 80)} ({who})"
    msg["From"] = os.environ.get("RFQ_FROM", "Genichi RFQ <service@genichi-tool.com>")
    msg["To"] = RFQ_TO
    msg["Reply-To"] = formataddr((_one_line(str(fields["contact_name"]), 60), str(fields["contact_email"])))
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(idstring=ref, domain="genichi-tool.com")
    msg.set_content(body)
    return msg


def _deliver(ref: str, msg: EmailMessage, fields: dict[str, object]) -> None:
    if DELIVERY == "smtp":
        host = os.environ["RFQ_SMTP_HOST"]
        port = int(os.environ.get("RFQ_SMTP_PORT", "465"))
        user, password = os.environ.get("RFQ_SMTP_USER"), os.environ.get("RFQ_SMTP_PASSWORD")
        context = ssl.create_default_context()
        if os.environ.get("RFQ_SMTP_SSL", "1") == "1":
            smtp = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
            smtp.starttls(context=context)
        with smtp:
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
    elif DELIVERY == "webhook":
        payload = dict(fields, reference=ref, to=RFQ_TO, subject=msg["Subject"], body=msg.get_content())
        req = urllib.request.Request(
            os.environ["RFQ_WEBHOOK_URL"],
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Genichi-Secret": os.environ.get("RFQ_WEBHOOK_SECRET", "")},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"webhook returned HTTP {resp.status}")
    elif DELIVERY == "file":
        OUTBOX.mkdir(parents=True, exist_ok=True)
        (OUTBOX / f"{ref}.eml").write_bytes(bytes(msg))
    else:
        raise RuntimeError(f"unknown RFQ_DELIVERY {DELIVERY!r}")


# ---------------------------------------------------------------- the tool
Long = Annotated[str | None, Field(max_length=2000)]


@server.tool(
    name="submit_rfq",
    title="Send quote request to Genichi Tool",
    description=(
        "Email a request for quotation (RFQ) for a custom-manufactured product or part to Genichi Tool Co., Ltd. "
        "(Taichung, Taiwan) at service@genichi-tool.com. Sends exactly the fields provided, with Reply-To set to "
        "contact_email so Genichi Tool replies to the customer directly, and returns a reference number. "
        "Use it only after the user has reviewed the final request and agreed to send it. "
        "Files cannot be attached; pass links the user chose to share in drawing_links."
    ),
    annotations=ToolAnnotations(
        title="Send quote request to Genichi Tool",
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    ),
)
async def submit_rfq(
    contact_name: Annotated[str, Field(min_length=1, max_length=100, description="Customer's name")],
    contact_email: Annotated[str, Field(max_length=254, description="Email address Genichi Tool should reply to")],
    product_name: Annotated[str, Field(min_length=2, max_length=150, description="Short name of the product or part")],
    description: Annotated[
        str,
        Field(
            min_length=20,
            max_length=6000,
            description="What the item is and does, how it is used, and every requirement the user gave",
        ),
    ],
    quantity: Annotated[
        str, Field(min_length=1, max_length=200, description="Quantity or quantities to quote, e.g. '500 pcs; 2,000 pcs'")
    ],
    company: Annotated[str | None, Field(max_length=150, description="Company name")] = None,
    country: Annotated[str | None, Field(max_length=80, description="Country or region for delivery")] = None,
    phone: Annotated[str | None, Field(max_length=50, description="Phone or messaging contact")] = None,
    material: Annotated[str | None, Field(max_length=300, description="Material or grade, if known")] = None,
    dimensions_and_tolerances: Long = None,
    finish_and_treatment: Annotated[
        str | None, Field(max_length=300, description="Surface finish, plating, coating, heat treatment, marking")
    ] = None,
    target_unit_price: Annotated[str | None, Field(max_length=100, description="Target price per unit, with currency")] = None,
    needed_by: Annotated[str | None, Field(max_length=100, description="Date the first delivery is needed")] = None,
    drawing_links: Annotated[
        list[Annotated[str, Field(max_length=500)]] | None,
        Field(max_length=10, description="https links the user chose to share: drawings, CAD, photos"),
    ] = None,
    notes: Long = None,
    ctx: Context | None = None,
) -> RFQReceipt:
    contact_email = contact_email.strip()
    if not EMAIL_RE.match(contact_email):
        raise ToolError("contact_email is not a valid email address. Ask the user for the address Genichi should reply to.")
    for n, link in enumerate(drawing_links or [], 1):
        if not link.startswith("https://"):  # tool errors are logged, so name the link by position, not content
            raise ToolError(f"drawing_links must be https URLs; link {n} is not.")

    ip = _client_ip(ctx)
    if not (
        _allow("day", MAX_PER_DAY, 86400)
        and (_shared_ip(ip) or _allow(f"ip:{ip}", MAX_PER_IP_HOUR, 3600))
        and _allow(f"email:{contact_email.lower()}", MAX_PER_EMAIL_HOUR, 3600)
    ):
        raise ToolError(
            f"Too many requests were sent recently. Please try again later, or email the request to {RFQ_TO} directly."
        )

    ref = f"RFQ-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(2).upper()}"
    fields = {
        "contact_name": contact_name,
        "contact_email": contact_email,
        "company": company,
        "country": country,
        "phone": phone,
        "product_name": product_name,
        "description": description,
        "quantity": quantity,
        "material": material,
        "dimensions_and_tolerances": dimensions_and_tolerances,
        "finish_and_treatment": finish_and_treatment,
        "target_unit_price": target_unit_price,
        "needed_by": needed_by,
        "drawing_links": drawing_links,
        "notes": notes,
    }
    fields = {k: v for k, v in fields.items() if v}
    msg = _build_email(ref, fields)
    try:
        await anyio.to_thread.run_sync(_deliver, ref, msg, fields)
    except Exception as exc:  # delivery problems are reported without echoing the request back
        log.error("rfq %s delivery failed: %s", ref, type(exc).__name__)
        raise ToolError(
            f"The request could not be delivered right now ({type(exc).__name__}). "
            f"Please try again later, or email it to {RFQ_TO} directly."
        ) from None
    log.info("rfq %s delivered via %s", ref, DELIVERY)
    return RFQReceipt(
        reference=ref,
        sent_to=f"Genichi Tool Co., Ltd. <{RFQ_TO}>",
        reply_to=contact_email,
        next_steps=(
            f"Genichi Tool will reply to {contact_email}. "
            f"To add drawings or files, email them to {RFQ_TO} with {ref} in the subject."
        ),
    )


# ---------------------------------------------------------------- HTTP
# Claude and the connector directory show the favicon of the server's site next to the connector.
STATIC = Path(__file__).with_name("static")
ICON_CACHE = {"Cache-Control": "public, max-age=86400"}


@server.custom_route("/", methods=["GET"])
async def home(_: Request) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html><head><meta charset="utf-8"><title>Genichi Tool RFQ</title>'
        '<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" type="image/png" href="/icon.png">'
        "</head><body><pre>Genichi Tool RFQ MCP server. MCP endpoint: /mcp (streamable HTTP).\n"
        f'Source, privacy and documentation: <a href="{REPO_URL}">{REPO_URL}</a></pre></body></html>\n'
    )


@server.custom_route("/favicon.ico", methods=["GET"])
async def favicon(_: Request) -> FileResponse:
    return FileResponse(STATIC / "favicon.ico", media_type="image/x-icon", headers=ICON_CACHE)


@server.custom_route("/icon.png", methods=["GET"])
async def icon(_: Request) -> FileResponse:
    return FileResponse(STATIC / "icon.png", media_type="image/png", headers=ICON_CACHE)


def create_app():
    hosts = [h.strip() for h in os.environ.get("RFQ_ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(hosts), allowed_hosts=hosts, allowed_origins=["https://claude.ai"]
    )
    return server.streamable_http_app(stateless_http=True, json_response=True, transport_security=security)


if __name__ == "__main__":
    # One worker, whatever WEB_CONCURRENCY says (Heroku's Python buildpack sets it): the rate limits
    # live in this process's memory, and uvicorn can only start workers from an import string.
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), proxy_headers=True, workers=1)
