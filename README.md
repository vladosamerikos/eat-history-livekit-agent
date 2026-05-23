# Eat History - LiveKit Voice Agent

This directory contains the LiveKit voice agent for Eat History. It acts as an interactive voice assistant that helps users log meals, check existing catalog items, log their weight, and manage daily nutrition history.

## Features

- **Multi-language Support:** Dynamic prompt loading based on user locale (`es`, `en`, `uk`) from the `prompts/` folder.
- **STT (Speech-to-Text):** Powered by Google Cloud Speech-to-Text (using Chirp).
- **LLM (Language Model):** Google Vertex Gemini.
- **TTS (Text-to-Speech):** Powered by Google Cloud Text-to-Speech (utilizing HD voices).
- **MCP Integration:** Connects to the NestJS backend's Model Context Protocol (MCP) server dynamically, allowing real-time retrieval and modification of catalog foods, logs, and weights.

## Project Structure

- `agent.py`: Main entry point for the LiveKit agent.
- `prompts/`: System instructions for each supported language.
  - `es.txt` - Spanish prompt
  - `en.txt` - English prompt
  - `uk.txt` - Ukrainian prompt
- `Dockerfile` & `docker-compose.production.yml`: Ready for containerized deployment.

## Running the Agent

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with necessary credentials:
   ```env
   LIVEKIT_URL=...
   LIVEKIT_API_KEY=...
   LIVEKIT_API_SECRET=...
   GOOGLE_APPLICATION_CREDENTIALS=...
   ```

3. Start the agent:
   ```bash
   python agent.py dev
   ```
