# LiveKit Voice Agent

A LiveKit-powered voice AI agent framework that demonstrates how to build realtime conversational AI with MCP (Model Context Protocol) server integration.

## Features

- 🎤 Natural voice conversations with low latency
- 🔄 Real-time voice interaction with interruption handling
- 🛠️ Tool integration via MCP servers
- 🎯 Multiple provider options (OpenAI, Deepgram, Cartesia, etc.)
- 🔌 Extensible architecture for custom tools and agents

## Prerequisites

- Python 3.9 or later
- API Keys:
  - Gemini API key
  - Deepgram API key
  - LiveKit credentials (optional - only if deploying to LiveKit Cloud)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

**Required variables:**
- `GEMINI_API_KEY` - Gemini API key
- `DEEPGRAM_API_KEY` - Deepgram API key

**Optional for LiveKit Cloud deployment:**
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret


### 4. Run the Agent

```bash
# Basic agent
python3 agent.py console
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   LiveKit   │──b─▶│ Voice Agent  │───▶ │ MCP Servers │
│   Client    │     │              │     │   (Tools)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              ┌─────▼────┐  ┌────▼─────┐
              │ Deepgram │  │  Gemini  │
              │ STT/TTS  │  │   LLM    │
              └──────────┘  └──────────┘
```


## Voice Pipeline Configuration

The agent uses a modular voice pipeline with swappable components:

### Speech-to-Text (STT)
- **Default**: Deepgram Nova-2 (highest accuracy)
- Alternatives: AssemblyAI, Azure Speech, Whisper

### Large Language Model (LLM)
- **Default**: Gemini 2.5 Flash (fast, cost-effective)
- Alternatives: Anthropic Claude, Google Gemini

### Text-to-Speech (TTS)
- **Default**: Deepgram (natural, versatile)
- Alternatives: Cartesia (fastest), ElevenLabs (highest quality)

### Voice Activity Detection (VAD)
- **Default**: Silero VAD (reliable voice detection)

