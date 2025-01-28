import asyncio
import logging
import os
import sys

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
from neonize.utils import log, get_message_type
from neonize.utils.enum import ReceiptType, MediaType

sys.path.insert(0, os.getcwd())


def interrupted(*_):
    event.set()


log.setLevel(logging.INFO)
# signal.signal(signal.SIGINT, interrupted)


client = NewAClient("db.sqlite3")


@client.event(ConnectedEv)
async def on_connected(_: NewAClient, __: ConnectedEv):
    log.info("⚡ Connected")


async def handler(client: NewAClient, message: MessageEv) -> dict:
    result = {"audio_path": str(message.Message.audioMessage.directPath),
    "audio_enc_hash": message.Message.audioMessage.fileEncSHA256,
    "audio_file_hash": message.Message.audioMessage.fileSHA256,
    "audio_media_key": message.Message.audioMessage.mediaKey,
    "audio_file_length": message.Message.audioMessage.fileLength,
    "audio_media_type": MediaType(2),
    "audio_mms_type": str(2)}
    chat = message.Info.MessageSource.Chat
    return message, result, chat



@client.event(PairStatusEv)
async def PairStatusMessage(_: NewAClient, message: PairStatusEv):
    log.info(f"logged as {message.ID.User}")

async def handle_audio_message(message, result, chat):
    direct_path = result.get('audio_path')
    enc_file_hash = result.get('audio_enc_hash')
    file_hash = result.get('audio_file_hash')
    media_key = result.get('audio_media_key')
    file_length = result.get('audio_file_length')
    media_type = result.get('audio_media_type')
    mms_type = result.get('audio_mms_type')
    reply_message = message
    # Download audio file from WhatsApp
    audio_data = await client.download_media_with_path(direct_path=direct_path, enc_file_hash=enc_file_hash, file_hash=file_hash, media_key=media_key, file_length=file_length, media_type=media_type, mms_type=mms_type)
    with open(f"./messages/audio-{str(file_length)}.webm","wb") as f:
        f.write(audio_data)
    # Transcribe audio using Groq API
    transcription = await transcribe_audio_groq(audio_path=f"./messages/audio-{str(file_length)}.webm", prompt=None, language='pt')
    os.remove(f"./messages/audio-{str(file_length)}.webm")
    # Reply with transcription
    await client.reply_message(
        message=f"Transcrição automática: \n\n{transcription}", 
        quoted=reply_message, 
        to=chat
    )

async def start():
    await client.connect()

@client.event(MessageEv)
async def on_message(client: NewAClient, message: MessageEv):
    is_audio = get_message_type(message)
    if "audioMessage {" in str(is_audio):
        message, result, chat = await handler(client, message)
        await handle_audio_message(message=message, result=result, chat=chat)
    



# Main application
if __name__ == "__main__":
    asyncio.run(start())
[]