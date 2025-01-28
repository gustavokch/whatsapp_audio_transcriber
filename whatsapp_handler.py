
import asyncio
import logging
import os
import sys
import signal

from groq_transcriber import transcribe_audio_groq
from datetime import timedelta
from neonize.aioze.client import NewAClient
from neonize.events import (
    ConnectedEv,
    MessageEv,
    PairStatusEv,
    event
)
from neonize.types import MessageServerID
from neonize.utils import log as neonize_log, get_message_type
from neonize.utils.enum import ReceiptType, MediaType

sys.path.insert(0, os.getcwd())

# Setup logging to different files
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
os.makedirs("./messages", exist_ok=True)

def interrupted(*_):
    event.set()

neonize_log.setLevel(logging.INFO)
signal.signal(signal.SIGINT, interrupted)

# Configure separate log files for different levels
logging.basicConfig(level=logging.DEBUG,  # Set default level to DEBUG to capture all levels
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    handlers=[
                        logging.FileHandler(os.path.join(log_dir, 'debug.log')),
                        logging.StreamHandler()  # Optionally keep console logging for debug
                    ])

# Create separate logger for INFO and ERROR levels, directing to different files
info_logger = logging.getLogger("info_logger")
info_logger.setLevel(logging.INFO)
info_handler = logging.FileHandler(os.path.join(log_dir, 'info.log'))
info_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
info_logger.addHandler(info_handler)

error_logger = logging.getLogger("error_logger")
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler(os.path.join(log_dir, 'error.log'))
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
error_logger.addHandler(error_handler)


debug_logger = logging.getLogger(__name__) # get logger for current module
neonize_log.setLevel(logging.WARNING) # Keep neonize logs minimal


event = asyncio.Event() # Initialize asyncio event

client = NewAClient("db.sqlite3") # Initialize WhatsApp client


@client.event(ConnectedEv)
async def on_connected(_: NewAClient, __: ConnectedEv) -> None:
    """
    Event handler for when the client connects to WhatsApp.
    Logs a message indicating successful connection.
    """
    info_logger.info("⚡ Connected to WhatsApp")


async def handler(client: NewAClient, message: MessageEv) -> tuple[MessageEv, dict, str]:
    """
    Handles incoming messages, extracts relevant audio information.

    Args:
        client (NewAClient): The WhatsApp client instance.
        message (MessageEv): The message event.

    Returns:
        tuple[MessageEv, dict, str]: A tuple containing the message event,
                                     a dictionary with audio details, and the chat ID.
    """
    debug_logger.debug(f"Handling message from chat: {message.Info.MessageSource.Chat}")
    result: dict[str, str | int | MediaType] = { # Type hinting for result dictionary
        "audio_path": str(message.Message.audioMessage.directPath),
        "audio_enc_hash": message.Message.audioMessage.fileEncSHA256,
        "audio_file_hash": message.Message.audioMessage.fileSHA256,
        "audio_media_key": message.Message.audioMessage.mediaKey,
        "audio_file_length": message.Message.audioMessage.fileLength,
        "audio_media_type": MediaType(2),
        "audio_mms_type": str(2)
    }
    chat = message.Info.MessageSource.Chat
    return message, result, chat



@client.event(PairStatusEv)
async def PairStatusMessage(_: NewAClient, message: PairStatusEv) -> None:
    """
    Event handler for pair status messages (e.g., logged in as).
    Logs the user ID upon successful login.
    """
    info_logger.info(f"Logged in as user ID: {message.ID.User}")

async def handle_audio_message(message: MessageEv, result: dict, chat: str) -> None:
    """
    Downloads, transcribes, and replies to audio messages.

    Args:
        message (MessageEv): The original message event.
        result (dict): Dictionary containing audio file details.
        chat (str): The chat ID to reply to.
    """
    debug_logger.debug("Handling audio message...")
    direct_path = result.get('audio_path')
    enc_file_hash = result.get('audio_enc_hash')
    file_hash = result.get('audio_file_hash')
    media_key = result.get('audio_media_key')
    file_length = result.get('audio_file_length')
    media_type = result.get('audio_media_type')
    mms_type = result.get('audio_mms_type')
    reply_message = message

    try:
        # Download audio file from WhatsApp
        info_logger.info(f"Downloading audio message: {direct_path}")
        audio_data = await client.download_media_with_path(
            direct_path=direct_path,
            enc_file_hash=enc_file_hash,
            file_hash=file_hash,
            media_key=media_key,
            file_length=file_length,
            media_type=media_type,
            mms_type=mms_type
        )
        file_path = f"./messages/audio-{str(file_length)}.webm"
        os.makedirs("./messages", exist_ok=True) # Ensure directory exists
        with open(file_path,"wb") as f:
            f.write(audio_data)
        info_logger.info(f"Audio message downloaded and saved to: {file_path}")

        # Transcribe audio using Groq API
        info_logger.info(f"Transcribing audio file: {file_path}")
        transcription = await transcribe_audio_groq(audio_path=file_path, prompt=None, language='pt')
        info_logger.info("Audio transcription completed.")

        os.remove(file_path) # Clean up audio file after transcription
        debug_logger.debug(f"Temporary audio file removed: {file_path}")

        # Reply with transcription
        transcription = transcription.lstrip(' ')
        reply_text = f"Transcrição automática: \n\n{transcription}"
        
        info_logger.info(f"Replying with transcription to chat: {chat}")
        await client.reply_message(
            message=reply_text,
            quoted=reply_message,
            to=chat
        )
        info_logger.info("Reply sent successfully.")


    except FileNotFoundError as e:
        error_logger.error(f"File not found error during audio processing: {e}", exc_info=True)
        await client.reply_message(message="Erro ao processar o áudio (Arquivo não encontrado).", quoted=reply_message, to=chat)
    except Exception as e:
        error_logger.error(f"Error handling audio message: {e}", exc_info=True)
        await client.reply_message(message="Erro ao processar o áudio. Por favor, tente novamente.", quoted=reply_message, to=chat)


async def start() -> None:
    """
    Starts the WhatsApp client and event loop.
    """
    info_logger.info("Starting WhatsApp client...")
    try:
        await client.connect() # Connect to WhatsApp
        info_logger.info("Client connected and running.")
        await event.wait() # Keep the application running until interrupted
    except Exception as e:
        error_logger.error(f"Failed to start client: {e}", exc_info=True)
    finally:
        info_logger.info("Client application finished.")


@client.event(MessageEv)
async def on_message(client: NewAClient, message: MessageEv) -> None:
    """
    Event handler for incoming messages.
    Checks if the message is an audio message and processes it accordingly.

    Args:
        client (NewAClient): The WhatsApp client instance.
        message (MessageEv): The message event.
    """
    message_type = get_message_type(message) # Determine message type
    debug_logger.debug(f"Received message of type: {message_type}")

    if "audioMessage {" in str(message_type): # Check if it's an audio message
        debug_logger.debug("Message is an audio message.")
        try:
            message_data, result, chat = await handler(client, message) # Extract message data
            await handle_audio_message(message=message_data, result=result, chat=chat) # Process audio message
        except Exception as e:
            error_logger.error(f"Error processing audio message in on_message handler: {e}", exc_info=True)
    else:
        debug_logger.debug(f"Ignoring non-audio message of type: {message_type}")



# Main application entry point
if __name__ == "__main__":
    asyncio.run(start())