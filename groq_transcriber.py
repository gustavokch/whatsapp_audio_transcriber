import os
import aiofiles
from groq import AsyncGroq
from typing import Optional
from dotenv import load_dotenv
import logging

# Setup logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

debug_logger = logging.getLogger(__name__)
debug_logger.setLevel(logging.DEBUG)
debug_handler = logging.FileHandler(os.path.join(log_dir, 'debug_groq_transcriber.log'))
debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
debug_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_handler)


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
        model (str, optional): Model to use for transcription. Defaults to "whisper-large-v3".
        prompt (str, optional): Context or spelling guidance for transcription. Defaults to None.
        language (str, optional): Language code (e.g., "pt" for Portuguese). Defaults to None (auto-detect).
        temperature (float, optional): Sampling temperature for transcription. Defaults to 0.0.

    Returns:
        str: The transcribed text

    Raises:
        FileNotFoundError: If the audio file doesn't exist
        Exception: For API or processing errors
    """
    debug_logger.debug(f"Starting audio transcription for file: {audio_path}")

    # Verify file exists
    if not os.path.exists(audio_path):
        error_message = f"Audio file not found: {audio_path}"
        debug_logger.error(error_message)
        raise FileNotFoundError(error_message)

    try:
        # Initialize async Groq client
        debug_logger.debug("Initializing AsyncGroq client.")
        client = AsyncGroq(api_key=api_key)
        debug_logger.debug("AsyncGroq client initialized successfully.")

        # Open and read the audio file in binary mode asynchronously
        debug_logger.debug(f"Opening audio file: {audio_path} for reading.")
        async with aiofiles.open(audio_path, 'rb') as file:
            audio_data = await file.read()
        debug_logger.debug(f"Audio file: {audio_path} read successfully.")

        # Log API key and transcription start
        debug_logger.debug(f"Groq API Key: {'API key is set' if api_key != 'API key not set' else 'API key not set'}")
        debug_logger.debug("Transcribing with Groq API...")

        # Model and language selection logic
        if language and language[:2] == "en" and model == "whisper-large-v3":
            language = "en" # Ensure language is explicitly "en"
            model="whisper-large-v3"
            debug_logger.debug(f"Using model: {model} with language: {language}")
        elif model == "distil-whisper-large-v3-en":
            language = None # Language is not needed for distil-whisper-large-v3-en
            model="distil-whisper-large-v3-en"
            debug_logger.debug(f"Using model: {model} (language auto-detected)")
        elif language:
            model = "whisper-large-v3" # Default to whisper-large-v3 for other languages
            debug_logger.debug(f"Using model: {model} with language: {language}")
        else:
            model = "whisper-large-v3" # Default model if no specific conditions met
            language = None # Let API auto-detect language if not specified
            debug_logger.debug(f"Using model: {model} (language auto-detected)")


        # Create transcription request to Groq API
        debug_logger.debug("Sending transcription request to Groq API.")
        response = await client.audio.transcriptions.create(
            file=(audio_path, audio_data),
            model=model,
            prompt=prompt,
            response_format='json',
            language=language,
            temperature=temperature
        )
        debug_logger.debug("Transcription request completed successfully.")

        return response.text # Return transcribed text

    except FileNotFoundError as fnf_error:
        debug_logger.error(f"File not found during transcription: {fnf_error}", exc_info=True)
        raise # Re-raise FileNotFoundError to be handled upstream
    except Exception as e:
        error_message = f"Transcription failed: {str(e)}"
        debug_logger.error(error_message, exc_info=True) # Log detailed error information
        raise Exception(error_message) from e # Re-raise exception to be handled upstream