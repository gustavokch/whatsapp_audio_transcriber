# WhatsApp Audio Transcription Bot

A WhatsApp bot that automatically transcribes audio messages using the Groq API.

## Features

- Automatically detects and processes audio messages
- Transcribes audio using Groq's Whisper API
- Replies with the transcription in the chat
- Supports multiple languages (default: Portuguese)
- Asynchronous processing for efficient handling of messages

## Requirements

- Python 3.8 or higher
- WhatsApp account with WhatsApp Web access
- Groq API key (obtain from [Groq](https://www.groq.com/))
- Poetry for dependency management

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gustavokch/whatsapp_audio_transcriber && cd whatsapp_audio_transcriber
   ```

2. Install requirements:
   ```bash
   pip install neonize
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your Groq API key:
   ```bash
   echo "GROQ_API_KEY=your_api_key_here" > .env
   ```

## Usage

1. Run the application:
   ```bash
   python whatsapp_handler.py
   ```

2. Follow the on-screen instructions to pair your WhatsApp account with the bot.

3. Once connected, the bot will automatically process any incoming audio messages and reply with their transcriptions.

## Configuration

- The bot stores its database in `db.sqlite3` by default. You can modify this by changing the argument passed to `NewAClient`.
- The transcription language is set to Portuguese by default (`language='pt'`). You can modify this in the `handle_audio_message` function.

## Dependencies

- `aiofiles` - Asynchronous file handling
- `groq` - Groq API client for transcription
- `python-dotenv` - Environment variable management
- `asyncio` - Asynchronous programming support
- `typing` - Type hints for better code clarity

## Notes

- Make sure you have WhatsApp Web access enabled on your account.
- The bot stores audio files temporarily in the `messages` directory before transcription and cleanup.
- The Groq API key must be valid and properly configured in the `.env` file.

## License

MIT License
