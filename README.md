# WhatsApp Audio Transcription Bot

A WhatsApp bot that automatically transcribes audio messages using the Groq API.

## Features

- Automatically detects and processes audio messages.
- Automatically avoids transcribing messages from group chats and any numbers on ```./exclude.txt```.
- Transcribes audio using Groq's Whisper API.
- Replies with the transcription in the chat.
- Supports multiple languages (default: Portuguese).
- Asynchronous processing for efficient handling of messages.

## Requirements

- Python 3.8 or higher.
- WhatsApp account with WhatsApp Web access.
- Groq API key (obtain from [Groq](https://www.groq.com/)).
- `pip` and `python3-venv` installed.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gustavokch/whatsapp_audio_transcriber.git
   cd whatsapp_audio_transcriber
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory and add the necessary API keys:
   ```bash
   echo "GROQ_API_KEY=your_api_key_here" > .env
   ```

## Usage

1. Run the application:
   ```bash
   ./start.sh
   ```

2. Follow the on-screen instructions to pair your WhatsApp account with the bot.

3. Once connected, the bot will automatically process any incoming audio messages and reply with their transcriptions.

## Configuration

- The bot stores its database in `db.sqlite3` by default.
- The transcription language is set to Portuguese (`language='pt'`). Modify this in the `handle_audio_message` function.

## Environment Variables (`.env`)
Ensure your `.env` file includes:
```ini
GROQ_API_KEY=your_groq_api_key
CF_ACCOUNT_ID=your_cloudflare_account_id
CF_API_KEY=your_cloudflare_api_key
```

## Directory Structure
```
/whatsapp_audio_transcriber
├── .git/
├── cf_transcriber.py
├── create_service.py
├── exclude.txt
├── groq_transcriber.py
├── LICENSE
├── README.md
├── reqs_installed
├── requirements.txt
├── start.sh
├── whatsapp_handler_refactor.py
```

## Class & Function Descriptions

### `TranscriptionJob`
Handles the transcription of audio messages.

- `extract_audio_details()`: Extracts audio metadata from an incoming message.
- `handle_audio_message()`: Downloads, transcribes, and sends a response with the transcription.

### `cf_transcribe(audio_path, model, language)`
Uses Cloudflare's Whisper AI model to transcribe audio.

### `transcribe_audio_groq(audio_path, model, prompt, language, temperature)`
Transcribes audio using Groq's API.

### Event Handlers
- `on_connected()`: Logs when the bot connects to WhatsApp.
- `on_message()`: Handles incoming messages and triggers transcription when an audio message is detected.

## Dependencies
- `aiofiles`
- `groq`
- `python-dotenv`
- `asyncio`
- `typing`
- `neonize`

## Notes
- Ensure WhatsApp Web is enabled on your account.
- Temporary audio files are stored in the `messages` directory before cleanup.
- The bot excludes processing for numbers listed in `exclude.txt`.

## License
MIT License

