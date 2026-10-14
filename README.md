# Genichi Tool plugins for Claude

This repository holds the **Genichi Custom Manufacturing** plugin for Claude and the MCP server it connects to.

| Folder | Contents |
|---|---|
| [`genichi-custom-manufacturing/`](genichi-custom-manufacturing/) | The plugin: the `manufacturing-rfq` skill and the `genichi-rfq` connector reference. See its [README](genichi-custom-manufacturing/README.md) and [privacy policy](genichi-custom-manufacturing/PRIVACY.md). |
| [`server/`](server/) | Source of the `genichi-rfq` remote MCP server, which emails approved requests for quotation to service@genichi-tool.com. |
| `.claude-plugin/marketplace.json` | Lets Claude Code users add this repository as a plugin marketplace. |

## Install in Claude Code

```
/plugin marketplace add smokey7958/genichi-claude-plugin
/plugin install genichi-custom-manufacturing@genichi-tool
```

In claude.ai, the desktop and mobile apps, and Cowork, add the plugin from the directory under **Customize > Plugins** once it is listed.

## About Genichi Tool

Genichi Tool Co., Ltd. makes hand tools in Taichung, Taiwan, and takes on custom and OEM/ODM manufacturing. Contact: service@genichi-tool.com.
