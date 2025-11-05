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
python3 cli.py  # Authenticate
python3 cli.py --headless  # Start proxy on port 8084
```

## Starting the Proxy

After initial authentication, start the proxy server:

```bash
cd /opt/stacks/openai-chatgpt-max-proxy
nohup python3 cli.py --headless > proxy.log 2>&1 &
```

The proxy will run on port 8084 and provide OpenAI-compatible endpoints:
- `/v1/models` - List available models
- `/models` - Alias for `/v1/models` (Letta compatibility)
- `/v1/chat/completions` - Chat completions endpoint

To check if it's running:
```bash
curl http://192.168.50.90:8084/models
```

## Status

🚧 **Under Development** - Being ported from anthropic-claude-max-proxy

See [anthropic-claude-max-proxy](https://github.com/oculairmedia/anthropic-claude-max-proxy) for the working sister project.
