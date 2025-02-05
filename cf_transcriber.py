import asyncio
import aiohttp
import aiofiles
import base64
import os
import argparse
import numpy as np
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

class CloudflareAITranscriber:
    def __init__(self, account_id: str, api_token: str, model: Optional[str] = None, language: Optional[str] = "en"):
        """Initialize the transcriber with Cloudflare credentials."""
        self.model = "@cf/openai/whisper-large-v3-turbo" if model is None else model
        self.account_id = account_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{self.model}"
        self.language = language if language is not None else "en"
        print("CF Account ID: "+account_id+"\n"+"CF API Token: "+api_token)

    async def _encode_audio_file(self, file_path: str) -> str:
        """Read and encode audio file to base64."""
        async with aiofiles.open(file_path, 'rb') as file:
            audio_content = await file.read()
            return base64.b64encode(audio_content).decode('utf-8')

    async def _read_audio_as_uint8(self, file_path: str) -> List[int]:
        """Read audio file as 8-bit unsigned integers."""
        async with aiofiles.open(file_path, 'rb') as file:
            audio_content = await file.read()
            # Convert bytes to numpy array of uint8
            audio_array = np.frombuffer(audio_content, dtype=np.uint8)
            # Convert to regular list and ensure values are between 0-255
            return audio_array.tolist()

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        """Transcribe audio using Cloudflare's Whisper model."""
        if self.model == "@cf/openai/whisper-large-v3-turbo" or self.model == "@cf/openai/whisper-large-v3":
            clean_model = self.model.replace("/@cf/openai/", "")
            encoded_audio = await self._encode_audio_file(audio_path)
            if language == None:
                language == "en"
            print("Language passed to Whisper: "+str(language))
            payload = {
                "model": clean_model,
                "audio": encoded_audio,
                "language": language,
                "vad_filter": "false"
            }
        else:  # whisper model
            audio_data = await self._read_audio_as_uint8(audio_path)
            payload = {
                "audio": audio_data
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Transcription failed: {error_text}")
                
                result = await response.json()
                return result

class AudioProcessor:
    def __init__(self, transcriber: CloudflareAITranscriber, language: Optional[str] = None):
        self.transcriber = transcriber
        self.language = language
        
    async def process_audio(self, audio_path: str, language: Optional[str] = None) -> dict:
        """Process an audio file and save the transcription."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        try:
            result = await self.transcriber.transcribe(audio_path, language=str(language))
            transcription = result.get('result', {}).get('text', '')
            return transcription
            
        except Exception as e:
            print(f"Error processing {audio_path}: {str(e)}")
            raise

async def cf_transcribe(audio_path: str, model: Optional[str] = None, language: Optional[str] = None):
    # Load environment variables
    load_dotenv()
    account_id = os.getenv("CF_ACCOUNT_ID")
    api_token = os.getenv("CF_API_KEY")
   
    if not account_id or not api_token:
        raise ValueError("Please set CF_ACCOUNT_ID and CF_API_KEY environment variables")
    if language == 'auto':
        language = 'en'
    # Initialize the transcriber and processor
    transcriber = CloudflareAITranscriber(account_id, api_token, model,  language=str(language))
    processor = AudioProcessor(transcriber, language=str(language))
    task = processor.process_audio(str(audio_path),  language=str(language))
    
    # Process all files concurrently
    result = await asyncio.gather(task, return_exceptions=True)
    result = str(result[0])
    print("Transcription: "+result)
    
    # Handle results
    if isinstance(result, Exception):
        print(f"Failed to process {audio_path}: {result[0]}")
    else:
        print(f"Successfully processed {audio_path}")
    return result

def main():
    parser = argparse.ArgumentParser(description='Transcribe audio using Cloudflare AI')
    parser.add_argument('audio_path', type=str, help='Path to the audio file to transcribe')
    parser.add_argument('--model', type=str, help='Model to use for transcription', default=None)
    args = parser.parse_args()
    
    asyncio.run(cf_transcribe(args.audio_path, args.model))

if __name__ == "__main__":
    main()