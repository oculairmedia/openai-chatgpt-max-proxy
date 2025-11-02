# OpenAI ChatGPT Max Proxy

Use your ChatGPT Plus/Pro subscription to access GPT-5 Codex models via API using official OpenAI OAuth authentication.

## Overview

This proxy enables you to:
- ✅ Use your **ChatGPT Plus/Pro subscription** instead of OpenAI Platform API credits
- ✅ Access **GPT-5 Codex** models with extended thinking capabilities  
- ✅ **OAuth authentication** using OpenAI's official flow (same as OpenAI Codex CLI)
- ✅ **OpenAI-compatible API** endpoints (`/v1/chat/completions`, `/v1/models`)
- ✅ **Automatic token refresh** - handles session expiration seamlessly
- ✅ **Reasoning variants** - Low/Medium/High effort levels
- ✅ **Letta compatibility** - Works with Letta AI agent framework

Sister project to [anthropic-claude-max-proxy](https://github.com/oculairmedia/anthropic-claude-max-proxy)

## ⚠️ Terms of Service & Usage Notice

**Important:** This proxy is designed for **personal development use only** with your own ChatGPT Plus/Pro subscription.

**NOT Intended For:**
- ❌ Commercial API resale
- ❌ Multi-user services
- ❌ Violating OpenAI's Terms

**For production use, use the [OpenAI Platform API](https://platform.openai.com/)**

## Quick Start

```bash
git clone https://github.com/oculairmedia/openai-chatgpt-max-proxy.git
cd openai-chatgpt-max-proxy
pip install -r requirements.txt
python cli.py  # Authenticate
python cli.py --headless  # Start proxy on port 8083
```

## Status

🚧 **Under Development** - Being ported from anthropic-claude-max-proxy

See [anthropic-claude-max-proxy](https://github.com/oculairmedia/anthropic-claude-max-proxy) for the working sister project.
