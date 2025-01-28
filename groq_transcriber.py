import os
import aiofiles
from groq import AsyncGroq
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY", "API key not set")

async def transcribe_audio_groq(
    audio_path: str,
    model: Optional[str] = "whisper-large-v3",
    prompt: Optional[str] = None,
    language: Optional[str] = None,
    temperature: float = 0.0
) -> str:
    """
    Asynchronously transcribe an audio file using Groq's API.

    Args:
        audio_path (str): Path to the audio file
        prompt (str, optional): Context or spelling guidance for transcription
        language (str, optional): Language code (default: "en")
        temperature (float, optional): Sampling temperature (default: 0.0)

    Returns:
        str: The transcribed text

    Raises:
        FileNotFoundError: If the audio file doesn't exist
        Exception: For API or processing errors
    """
    # Verify file exists
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        # Initialize async client
        client = AsyncGroq(api_key=api_key)

        # Open and read the audio file
        async with aiofiles.open(audio_path, 'rb') as file:
            audio_data = await file.read()

        # Create transcription
        print("\n"+"Groq API Key: "+api_key+"\n")
        print("Transcribing with Groq API..."+"\n")
        if language[:2] == "en" and model == "whisper-large-v3":
            language = "en"
            model="whisper-large-v3"
        elif model == "distil-whisper-large-v3-en":
            language = None
            model="distil-whisper-large-v3-en"
        else:
            language=language
            model = "whisper-large-v3"


        response = await client.audio.transcriptions.create(
            file=(audio_path, audio_data),
            model=model,
            prompt=None,
            response_format='json',
            language=language,
            temperature=temperature
        )

        return response.text

    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")