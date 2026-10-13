# Genichi Tool RFQ MCP server

The remote MCP server behind the `genichi-custom-manufacturing` plugin. It exposes one tool, `submit_rfq`, which emails a request for quotation to service@genichi-tool.com. `genichi_rfq_server.py` documents what it sends and what it keeps, and every setting.

- Transport: streamable HTTP at `/mcp`, stateless, JSON responses
- Tool annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`, `openWorldHint: true`
- No authentication: anyone can submit an RFQ, as with a contact form. Each email goes only to `RFQ_TO`, and submissions are rate limited per contact email, per client IP and per day
- Built on the official MCP Python SDK (`mcp` 2.x)

## Test locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # on macOS or Linux: .venv/bin/pip
.venv/Scripts/python test_server.py
```

`test_server.py` starts the server with `RFQ_DELIVERY=file`, which writes `.eml` files instead of sending mail, and checks the tool list, annotations, one submission, input validation and the rate limit.

## Deploy to Heroku

```bash
heroku create genichi-rfq
heroku config:set -a genichi-rfq RFQ_DELIVERY=smtp RFQ_SMTP_HOST=imail.com.tw RFQ_SMTP_PORT=465 \
  RFQ_SMTP_USER=service@genichi-tool.com
git subtree push --prefix server https://git.heroku.com/genichi-rfq.git main
```

The mailbox sends to itself: `RFQ_TO` and `RFQ_FROM` default to service@genichi-tool.com, and port 465 uses implicit TLS (`RFQ_SMTP_SSL=1`, the default). Set `RFQ_SMTP_PASSWORD` in the Heroku dashboard (Settings → Config Vars) rather than on the command line, so it stays out of shell history, and update it whenever the mailbox password changes.

The server is published at `rfq.genichi-tool.com`, so the connector's domain matches the company's:

```bash
heroku domains:add rfq.genichi-tool.com -a genichi-rfq     # prints the DNS target for a CNAME record named rfq
heroku certs:auto:enable -a genichi-rfq
heroku config:set -a genichi-rfq RFQ_ALLOWED_HOSTS=<app>.herokuapp.com,rfq.genichi-tool.com
```

Once the CNAME resolves and `heroku certs:auto` shows the certificate as issued, the plugin's `.mcp.json` URL, `https://rfq.genichi-tool.com/mcp`, works. Check the endpoint with the MCP Inspector or as a custom connector in Claude.

To send through an existing n8n SMTP credential instead of storing SMTP details here, set `RFQ_DELIVERY=webhook`, `RFQ_WEBHOOK_URL` and `RFQ_WEBHOOK_SECRET`, and have the n8n workflow check the `X-Genichi-Secret` header before sending the `subject` and `body` fields to service@genichi-tool.com.
