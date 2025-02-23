import asyncio
import logging
import os
import sys
import signal
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple
from groq_transcriber import transcribe_audio_groq
from cf_transcriber import cf_transcribe
from neonize.aioze.client import NewAClient
from neonize.events import ConnectedEv, MessageEv, PairStatusEv, event
from neonize.types import MessageServerID
from neonize.utils import log as neonize_log, get_message_type
from neonize.utils.enum import ReceiptType, MediaType

sys.path.insert(0, os.getcwd())

# Constants

# Define the path to your exclusion list file
EXCLUDED_NUMBERS_FILE = "exclude.txt"

# Read numbers from the file and store them in a set
def load_excluded_numbers(filepath: str) -> set:
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            all_lines = file.readlines()
            f_line = {line.strip() for line in all_lines}
            file.close()
            return f_line
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Using default exclusions.")
        return set()

# Load excluded numbers
EXCLUDED_NUMBERS = load_excluded_numbers(EXCLUDED_NUMBERS_FILE)

print(EXCLUDED_NUMBERS)  # Debug: Print loaded numbers

WHISPER_PROMPT = """Transcreva com precisão, preservando enunciados conforme falados. Corrija erros ortográficos comuns sem alterar a intenção original. Use pontuação e capitalização de forma natural para facilitar a leitura. Foda-se. Amorzinho."""
LOG_DIR = "logs"
MESSAGES_DIR = "./messages"

# Setup logging
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MESSAGES_DIR, exist_ok=True)
shutil.rmtree(LOG_DIR, ignore_errors=True)
os.makedirs(LOG_DIR, exist_ok=True)

def interrupted(*_):
    """Signal handler for interrupting the application."""
    event.set()

neonize_log.setLevel(logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'debug.log')),
        logging.StreamHandler()
    ]
)

info_logger = logging.getLogger("info_logger")
info_logger.setLevel(logging.INFO)
info_handler = logging.FileHandler(os.path.join(LOG_DIR, 'info.log'))
info_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
info_logger.addHandler(info_handler)

error_logger = logging.getLogger("error_logger")
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler(os.path.join(LOG_DIR, 'error.log'))
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
error_logger.addHandler(error_handler)

debug_logger = logging.getLogger(__name__)
neonize_log.setLevel(logging.WARNING)

event = asyncio.Event()
client = NewAClient("db.sqlite3")

class TranscriptionJob:
    """Class to handle transcription jobs for audio messages."""

    def __init__(self, client: NewAClient, message: MessageEv):
        self.client = client
        self.message = message
        self.audio_details: Optional[Dict] = None
        self.chat_id: Optional[str] = None

    async def extract_audio_details(self) -> Tuple[MessageEv, Dict, str]:
        """Extract audio details from the message event."""
        debug_logger.debug(f"Handling message from chat: {self.message.Info.MessageSource.Chat}")
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

        direct_path = self.audio_details.get('audio_path')
        enc_file_hash = self.audio_details.get('audio_enc_hash')
        file_hash = self.audio_details.get('audio_file_hash')
        media_key = self.audio_details.get('audio_media_key')
        file_length = self.audio_details.get('audio_file_length')
        media_type = self.audio_details.get('audio_media_type')
        mms_type = self.audio_details.get('audio_mms_type')

        try:
            # Download audio file from WhatsApp
            info_logger.info(f"Downloading audio message: {direct_path}")
            audio_data = await self.client.download_media_with_path(
                direct_path=direct_path,
                enc_file_hash=enc_file_hash,
                file_hash=file_hash,
                media_key=media_key,
                file_length=file_length,
                media_type=media_type,
                mms_type=mms_type
            )
            file_path = f"{MESSAGES_DIR}/audio-{str(file_length)}.webm"
            with open(file_path, "wb") as f:
                f.write(audio_data)
            info_logger.info(f"Audio message downloaded and saved to: {file_path}")

            # Transcribe audio using Groq API
            info_logger.info(f"Transcribing audio file: {file_path}")
            transcription = await transcribe_audio_groq(audio_path=file_path, prompt=WHISPER_PROMPT, language='pt')
            #transcription = await cf_transcribe(audio_path=file_path, model='@cf/openai/whisper-large-v3-turbo', language='pt')
            info_logger.info("Audio transcription completed.")

            os.remove(file_path)  # Clean up audio file after transcription
            debug_logger.debug(f"Temporary audio file removed: {file_path}")

            # Reply with transcription
            transcription = transcription.lstrip(' ')
            transcription = '_' + transcription + '_'
            reply_text = f"*Transcrição automática:*\n\n{transcription}"

            info_logger.info(f"Replying with transcription to chat: {self.chat_id}")
            await self.client.reply_message(
                message=reply_text,
                quoted=self.message,
                to=self.chat_id
            )
            info_logger.info("Reply sent successfully.")

        except FileNotFoundError as e:
            error_logger.error(f"File not found error during audio processing: {e}", exc_info=True)
            await self.client.reply_message(message="Erro ao processar o áudio (Arquivo não encontrado).", quoted=self.message, to=self.chat_id)
        except Exception as e:
            error_logger.error(f"Error handling audio message: {e}", exc_info=True)
            await self.client.reply_message(message="Erro ao processar o áudio. Por favor, tente novamente.", quoted=self.message, to=self.chat_id)

@client.event(ConnectedEv)
async def on_connected(_: NewAClient, __: ConnectedEv) -> None:
    """Event handler for when the client connects to WhatsApp."""
    info_logger.info("⚡ Connected to WhatsApp")

@client.event(PairStatusEv)
async def PairStatusMessage(_: NewAClient, message: PairStatusEv) -> None:
    """Event handler for pair status messages (e.g., logged in as)."""
    info_logger.info(f"Logged in as user ID: {message.ID.User}")

@client.event(MessageEv)
async def on_message(client: NewAClient, message: MessageEv) -> None:
    """Event handler for incoming messages."""
    message_type = get_message_type(message)
    debug_logger.debug(f"Received message of type: {message_type}")
    send_reply = 1
    def exclude_number_handler(exclude_number):
        with open("exclude.txt", "r") as exclude_file:
            exclude_list = exclude_file.readlines()
            exclude_final = []

            for line in exclude_list:
                exclude_final.append(line.strip()+"\n")

            if exclude_number != None or exclude_number+"\n" or exclude_number not in exclude_list:
                print(f"Adding number {exclude_number.replace("\n","")} to exclude.txt")
                exclude_file.close()
                # os.remove("exclude.txt")
                with open("exclude.txt", "w") as exclude_append:
                    excluded = 0
                    for line in exclude_list:
                        stripped_line = str(line.strip())
                        if excluded != 1 and stripped_line not in exclude_final:
                                if stripped_line in exclude_list:
                                    exclude_final.append(stripped_line+"\n")
                    if exclude_number or exclude_number+"\n" not in exclude_final:
                        exclude_final.append(exclude_number+"\n")
                        excluded = 1
                    exclude_append.writelines(exclude_final)
                    exclude_append.close()

            else:
                with open("exclude.txt", "w") as exclude_write:
                    exclude_write.writelines(exclude_list)
                    print(f"Number {exclude_number.replace("\n","")} already in exclude.txt")
                    exclude_txt.close()

    def include_number_handler(include_number):    
        with open("exclude.txt", "r") as exclude_file:
            exclude_list = exclude_file.readlines()
            if include_number+"\n" or include_number in exclude_list:
                print(f"Removing number {include_number} from exclude.txt")
                lines = exclude_list
                updated_lines = []
                include_line=include_number.strip()
                count = len(exclude_list)
                def check_line():
                    n = 0
                    for line in lines:
                        stripped_line = line.strip()
                        if line != "\n" and stripped_line != include_line:
                            updated_lines.append(stripped_line)
                            updated_lines.append("\n")
                        if include_line in stripped_line:
                            updated_lines.remove(include_line)
                        n = n + 1
                    return n
                while True:
                    if check_line() == count:
                        break
                    check_line()    
            exclude_file.close()
        with open("exclude.txt", "w") as exclude_write:
            updated_lines.pop()
            exclude_write.writelines(updated_lines)
            exclude_write.close()

    if message.Info.MessageSource.IsFromMe == True and "/exclude " in str(message_type) or "/include " in str(message_type):
        with open("exclude.txt", "r") as exclude_txt:
            file_lines = exclude_txt.readlines()
            msg_string =  str(message_type)
            try:
                if msg_string.split("/exclude ")[1].split('"')[0]+"\n":
                    exclude_number = msg_string.split("/exclude ")[1].split('"')[0]
                    exclude_number_handler(exclude_number)      
                    EXCLUDED_NUMBERS = load_excluded_numbers(EXCLUDED_NUMBERS_FILE)
                    print("New exclusion list: "+str(EXCLUDED_NUMBERS))
            except:
                pass
            try:
                    include_number = msg_string.split("/include ")[1].split('"')[0]
                    include_number_handler(include_number)
                    EXCLUDED_NUMBERS = load_excluded_numbers(EXCLUDED_NUMBERS_FILE)
                    print("New exclusion list: "+str(EXCLUDED_NUMBERS))
                    # EXCLUDED_NUMBERS = load_excluded_numbers(EXCLUDED_NUMBERS_FILE)

            except:
                pass
    else:
        exclude_txt = None
 
    if 'text: "Erro ao processar o áudio.' in str(message_type):
        info_logger.info("Message is a transcription error message, ignoring...")
        send_reply = 0
    elif "audioMessage {" in str(message_type) and send_reply != 0:  # Check if it's an audio message
        debug_logger.debug("Message is an audio message.")
        if 'text: "*Transcrição automática:*' in str(message_type): 
                info_logger.info("Message is already a transcription, ignoring...")
                send_reply = 0
        try:
            # Skip group messages
            if message.Info.MessageSource.IsGroup:
                info_logger.info("Message is from a group, ignoring...")
                return

            # Check if sender is in exclusion list
            EXCLUDED_NUMBERS = load_excluded_numbers(EXCLUDED_NUMBERS_FILE)
            print(EXCLUDED_NUMBERS)  # Debug: Print loaded numbers  
            sender_jid = str(message.Info.MessageSource.Sender.User)
            phone_number = sender_jid
            #phone_number = phone_number.replace('"','')
            if phone_number in EXCLUDED_NUMBERS:
                info_logger.info(f"Sender {phone_number} is excluded. Skipping transcription.")
                return

            # Proceed with transcription
            if send_reply == 1:
                job = TranscriptionJob(client, message)
                await job.extract_audio_details()
                try:
                    info_logger.info("Message passed exclusion checks, transcribing...")
                    await asyncio.wait_for(job.handle_audio_message(), timeout=15.0)
                except asyncio.TimeoutError:
                    error_logger.error("Audio message handling timed out")

        except Exception as e:
            error_logger.error(f"Error processing transcription in on_message handler: {e}", exc_info=True)
            
    elif 'text: "*Transcrição automática:*' in str(message_type): 
        info_logger.info("Message is already a transcription, ignoring...")
        send_reply = 0
        
    else:
        debug_logger.debug(f"Ignoring non-audio message of type: {message_type}")

async def start() -> None:
    """Start the WhatsApp client and event loop."""
    info_logger.info("Starting WhatsApp client...")
    try:
        await client.connect()
        info_logger.info("Client connected and running.")
        await event.wait()
    except Exception as e:
        error_logger.error(f"Failed to start client: {e}", exc_info=True)
    finally:
        event.set()
        await client.disconnect()
        info_logger.info("Client application finished.")

async def main():
    try:
        await start()
    except KeyboardInterrupt:
        info_logger.info("KeyboardInterrupt received, shutting down...")
    finally:
        event.set()
        await client.disconnect()  # Ensure cleanup before exiting

if __name__ == "__main__":
    if not os.path.isfile("exclude.txt"):
        with open("exclude.txt", "x") as exclude_txt:
            exclude_txt.write
    asyncio.run(main())