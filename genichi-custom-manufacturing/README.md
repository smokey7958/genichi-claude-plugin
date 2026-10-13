# Genichi Custom Manufacturing

Need something made? This plugin helps Claude turn a product idea, sketch, photo, sample or existing part into a complete manufacturing request for quotation (RFQ), and, when you choose, sends it to **Genichi Tool Co., Ltd.** (元壹工具, Taichung, Taiwan) for a quote.

## What it does

- **Shapes the request.** Claude asks what the item has to do, then fills in what a factory needs to quote it: quantity, critical dimensions, material, finish and heat treatment, packaging, target price, timing and destination. It suggests a process route (CNC machining, forging, stamping, casting, molding, laser engraving and more) and flags design choices that drive cost. The finished RFQ is useful with any supplier.
- **Sends it, only if you say so.** Claude shows you the final request. After you confirm, it emails the request to Genichi Tool at service@genichi-tool.com and gives you a reference number. Genichi Tool replies to the email address you provide.

Genichi Tool makes hand tools (pliers, cutters, wire strippers, screwdrivers, sockets, tweezers), tool sets and laser-engraved products, and takes on custom, private-label and OEM/ODM projects. Every request is reviewed, including unusual ones, and answered with feasibility, process options and a quote.

## Components

| Component | What it is |
|---|---|
| Skill `manufacturing-rfq` | Instructions and reference checklists for building an RFQ. Runs inside Claude; it sends nothing on its own. |
| Connector `genichi-rfq` | A remote MCP server run by Genichi Tool, with one tool, `submit_rfq`. |

## What is sent, and where

`submit_rfq` is the only part of this plugin that sends data anywhere. It runs only when Claude calls it after you approve the request, and it sends exactly the fields shown to you:

- your name and reply email, plus company, phone and country if you give them
- the product details: name, description, quantity, material, dimensions and tolerances, finish, target price, needed-by date, notes, and any https links you chose to share

The data goes over HTTPS to Genichi Tool's MCP server (source code: [`server/`](https://github.com/smokey7958/genichi-claude-plugin/tree/main/server)), which emails it to service@genichi-tool.com with Reply-To set to your address. The server doesn't store requests, doesn't email anyone else, and logs only the reference number, time and delivery result. It does not read your conversation history, memory or uploaded files. Files can't be attached; send drawings by replying to Genichi Tool's email.

Privacy policy: [PRIVACY.md](https://github.com/smokey7958/genichi-claude-plugin/blob/main/genichi-custom-manufacturing/PRIVACY.md)

## Using it

Describe what you want made, for example:

- "I need 2,000 stainless steel brackets like this sketch. Who can make them and what should I specify?"
- "Can you help me get a quote for custom pliers with our logo on the handle?"
- "We want a private-label screwdriver set for our shop."

In claude.ai, the desktop and mobile apps, and Cowork, connect the **Genichi Tool RFQ** connector from the plugin's **Connectors** tab so Claude can send requests for you. Without it, Claude still prepares the RFQ and gives you the text to email yourself.

## Troubleshooting

- **Claude drafts the RFQ but doesn't offer to send it:** connect the Genichi Tool RFQ connector from the plugin's Connectors tab, then ask Claude to send the request.
- **"Too many requests":** the server limits how many requests one address can send per hour. Wait, or email the RFQ to service@genichi-tool.com directly.
- **Anything else:** email service@genichi-tool.com.

## License

MIT. See [LICENSE](LICENSE).
