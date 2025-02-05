import asyncio
import logging
import os
import sys
import signal
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple
from groq_transcriber import transcribe_audio_groq
from neonize.aioze.client import NewAClient
from neonize.events import ConnectedEv, MessageEv, PairStatusEv, event
from neonize.types import MessageServerID
from neonize.utils import log as neonize_log, get_message_type
from neonize.utils.enum import ReceiptType, MediaType

sys.path.insert(0, os.getcwd())

class WhatsAppTranscriber:
    # Constants
    WHISPER_PROMPT = """Transcreva com precisão, preservando enunciados conforme falados. Corrija erros ortográficos comuns sem alterar a intenção original. Use pontuação e capitalização de forma natural para facilitar a leitura. Foda-se. Amorzinho."""
    LOG_DIR = "logs"
    MESSAGES_DIR = "./messages"

    def __init__(self):
        self.setup_directories()
        self.setup_logging()
        self.event = asyncio.Event()
        self.client = NewAClient("db.sqlite3")
        self.setup_signal_handlers()
        self.setup_event_handlers()

    def setup_directories(self):
        """Initialize required directories."""
        for directory in [self.LOG_DIR, self.MESSAGES_DIR]:
            os.makedirs(directory, exist_ok=True)
        shutil.rmtree(self.LOG_DIR, ignore_errors=True)
        os.makedirs(self.LOG_DIR, exist_ok=True)

    def setup_logging(self):
        """Configure logging handlers."""
        neonize_log.setLevel(logging.WARNING)

        # Configure main logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.LOG_DIR, 'debug.log')),
                logging.StreamHandler()
            ]
        )

        # Info logger
        self.info_logger = logging.getLogger("info_logger")
        self.info_logger.setLevel(logging.INFO)
        info_handler = logging.FileHandler(os.path.join(self.LOG_DIR, 'info.log'))
        info_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.info_logger.addHandler(info_handler)

        # Error logger
        self.error_logger = logging.getLogger("error_logger")
        self.error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(os.path.join(self.LOG_DIR, 'error.log'))
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
        self.error_logger.addHandler(error_handler)

        # Debug logger
        self.debug_logger = logging.getLogger(__name__)

    def setup_signal_handlers(self):
        """Set up handlers for system signals."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        self.info_logger.info(f"Received signal {signum}")
        if not self.event.is_set():
            asyncio.get_event_loop().create_task(self.shutdown())

    def setup_event_handlers(self):
        """Set up WhatsApp event handlers."""
        self.client.event(ConnectedEv)(self.on_connected)
        self.client.event(PairStatusEv)(self.on_pair_status)
        self.client.event(MessageEv)(self.on_message)

    async def on_connected(self, _: NewAClient, __: ConnectedEv) -> None:
        """Handle connection event."""
        self.info_logger.info("⚡ Connected to WhatsApp")

    async def on_pair_status(self, _: NewAClient, message: PairStatusEv) -> None:
        """Handle pair status event."""
        self.info_logger.info(f"Logged in as user ID: {message.ID.User}")

    async def on_message(self, client: NewAClient, message: MessageEv) -> None:
        """Handle incoming messages."""
        message_type = get_message_type(message)
        self.debug_logger.debug(f"Received message of type: {message_type}")

        if self.should_ignore_message(message_type):
            return

        if "audioMessage {" in str(message_type):
            self.debug_logger.debug("Processing audio message")
            await self.handle_audio_message(message)

    def should_ignore_message(self, message_type: str) -> bool:
        """Determine if message should be ignored."""
        if 'text: "Erro ao processar o áudio.' in str(message_type):
            self.info_logger.info("Message is a transcription error message, ignoring...")
            return True
        elif 'text: "*Transcrição automática:*' in str(message_type):
            self.info_logger.info("Message is already a transcription, ignoring...")
            return True
        return False

    async def handle_audio_message(self, message: MessageEv) -> None:
        """Process audio messages."""
        if message.Info.MessageSource.IsGroup:
            self.info_logger.info("Message is from a group, ignoring...")
            return

        try:
            job = TranscriptionJob(self.client, message)
            await job.extract_audio_details()
            await asyncio.wait_for(job.handle_audio_message(), timeout=15.0)
        except asyncio.TimeoutError:
            self.error_logger.error("Audio message handling timed out")
        except Exception as e:
            self.error_logger.error(f"Error processing transcription: {e}", exc_info=True)

    async def start(self) -> None:
        """Start the WhatsApp client."""
        self.info_logger.info("Starting WhatsApp client...")
        try:
            await self.client.connect()
            self.info_logger.info("Client connected and running.")
            await self.event.wait()
        except Exception as e:
            self.error_logger.error(f"Failed to start client: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        self.info_logger.info("Shutting down...")
        self.event.set()
        if self.client:
            await self.client.disconnect()
        self.info_logger.info("Client disconnected.")
        if asyncio.get_event_loop().is_running():
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
            await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)
        sys.exit(0)

class TranscriptionJob:
    """Class to handle transcription jobs for audio messages."""

    def __init__(self, client: NewAClient, message: MessageEv):
        self.client = client
        self.message = message
        self.audio_details: Optional[Dict] = None
        self.chat_id: Optional[str] = None
        self.logger = logging.getLogger(__name__)

    async def extract_audio_details(self) -> Tuple[MessageEv, Dict, str]:
        """Extract audio details from the message event."""
        self.audio_details = {
            "audio_path": str(self.message.Message.audioMessage.directPath),
            "audio_enc_hash": self.message.Message.audioMessage.fileEncSHA256,
            "audio_file_hash": self.message.Message.audioMessage.fileSHA256,
            "audio_media_key": self.message.Message.audioMessage.mediaKey,
            "audio_file_length": self.message.Message.audioMessage.fileLength,
            "audio_media_type": MediaType(2),
            "audio_mms_type": str(2)
        }
        self.chat_id = self.message.Info.MessageSource.Chat
        return self.message, self.audio_details, self.chat_id

    async def handle_audio_message(self) -> None:
        """Download, transcribe, and reply to audio messages."""
        if not self.audio_details or not self.chat_id:
            raise ValueError("Audio details or chat ID not set.")

        file_path = f"{WhatsAppTranscriber.MESSAGES_DIR}/audio-{self.audio_details['audio_file_length']}.webm"

        try:
            # Download audio file
            audio_data = await self.client.download_media_with_path(
                direct_path=self.audio_details['audio_path'],
                enc_file_hash=self.audio_details['audio_enc_hash'],
                file_hash=self.audio_details['audio_file_hash'],
                media_key=self.audio_details['audio_media_key'],
                file_length=self.audio_details['audio_file_length'],
                media_type=self.audio_details['audio_media_type'],
                mms_type=self.audio_details['audio_mms_type']
            )

            with open(file_path, "wb") as f:
                f.write(audio_data)

            # Transcribe audio
            transcription = await transcribe_audio_groq(
                audio_path=file_path,
                prompt=WhatsAppTranscriber.WHISPER_PROMPT,
                language='pt'
            )

            # Clean up and reply
            os.remove(file_path)
            transcription = '_' + transcription.lstrip() + '_'
            reply_text = f"*Transcrição automática:*\n\n{transcription}"

            await self.client.reply_message(
                message=reply_text,
                quoted=self.message,
                to=self.chat_id
            )

        except FileNotFoundError as e:
            self.logger.error(f"File not found error: {e}", exc_info=True)
            await self.client.reply_message(
                message="Erro ao processar o áudio (Arquivo não encontrado).",
                quoted=self.message,
                to=self.chat_id
            )
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}", exc_info=True)
            await self.client.reply_message(
                message="Erro ao processar o áudio. Por favor, tente novamente.",
                quoted=self.message,
                to=self.chat_id
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

async def main():
    transcriber = WhatsAppTranscriber()
    try:
        await transcriber.start()
    except KeyboardInterrupt:
        await transcriber.shutdown()
 #       pass

if __name__ == "__main__":
    asyncio.run(main())