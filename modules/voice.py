import speech_recognition as sr
import re
from gtts import gTTS
import pygame
import time
import os

class SpeechRecognizer:
    def __init__(self, language='or-IN', engine='google'):
        self.language = language
        self.engine = engine
        self.r = sr.Recognizer()

    def transcribe(self, audio_file):
        with sr.AudioFile(audio_file) as source:
            audio = self.r.record(source)
        try:
            if self.engine == 'whisper':
                # Whisper transcription (requires whisper library)
                # This is a placeholder, as actual implementation might vary
                return self.r.recognize_whisper(audio, language='odia').lower(), 1.0
            else:
                # Google Speech Recognition
                result = self.r.recognize_google(audio, language=self.language, show_all=True)
                if result and 'alternative' in result:
                    top_alternative = result['alternative'][0]
                    return top_alternative['transcript'].lower(), top_alternative.get('confidence', 0.9)
                else:
                    return self.r.recognize_google(audio, language='en-IN', show_all=True)['alternative'][0]['transcript'].lower(), 0.5
        except sr.UnknownValueError:
            return None, 0.0
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None, 0.0

    def transcribe_from_mic(self, duration=3):
        with sr.Microphone() as source:
            print("Speak now...")
            audio = self.r.listen(source, phrase_time_limit=duration)
        
        # Save the recorded audio to a file for debugging
        with open("mic_recording.wav", "wb") as f:
            f.write(audio.get_wav_data())

        return self.transcribe("mic_recording.wav")

    def set_language(self, lang_code):
        self.language = lang_code

class IntentClassifier:
    def __init__(self):
        self.intents = {
            'emergency': ['help', 'sos', 'emergency', 'ସାହାଯ୍ୟ', 'ଡାକ୍ତର'],
            'medicine_query': ['medicine', 'pill', 'drug', 'ଔଷଧ', 'ଟାବଲେଟ'],
            'greeting': ['hello', 'hi', 'ନମସ୍କାର', 'ସୁପ୍ରଭାତ'],
            'acknowledge': ['yes', 'done', 'okay', 'ହଁ', 'ଠିକ୍ ଅଛି']
        }

    def classify(self, text: str):
        text = text.lower()
        for intent, keywords in self.intents.items():
            for keyword in keywords:
                if re.search(r'\b' + keyword + r'\b', text):
                    return intent, 1.0, {}
        return 'unknown', 0.0, {}

class TTSEngine:
    def __init__(self, language='or'):
        self.language = language
        pygame.mixer.init()

    def speak(self, text: str, save_path=None):
        if not text:
            print("Error: No text to speak.")
            return
        try:
            tts = gTTS(text=text, lang=self.language, slow=False)
            if save_path:
                tts.save(save_path)
                pygame.mixer.music.load(save_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            else:
                tts.save("response.mp3")
                pygame.mixer.music.load("response.mp3")
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                os.remove("response.mp3")
        except Exception as e:
            print(f"Error in TTS: {e}")

"""
Voice Module - Voice Assistant and Speech Processing
Handles voice input, speech recognition, and text-to-speech responses.
"""

import speech_recognition as sr
from gtts import gTTS
import pygame
import logging
import threading
from typing import Optional, Dict, Callable
from pathlib import Path
import re
import wave

import numpy as np

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - depends on runtime environment
    sd = None

logger = logging.getLogger(__name__)

class AudioHandler:
    """
    Handles low-level audio I/O operations.
    Records audio from microphone, saves WAV files, and plays audio files.
    """

    def __init__(self, sample_rate: int = 16000, chunk_duration: int = 3) -> None:
        """
        Initialize AudioHandler with sample rate and chunk duration.

        Args:
            sample_rate: Audio sample rate in Hz
            chunk_duration: Recording duration in seconds
        """
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.channels = 1
        self.dtype = "int16"
        self.input_device = None

        if sd is None:
            raise ImportError(
                "sounddevice is not installed. Install it with: pip install sounddevice"
            )

        self._select_input_device()

    def _select_input_device(self) -> None:
        """
        Select an input audio device.
        If multiple microphones exist, prefer default input device.
        """
        try:
            devices = sd.query_devices()
            input_devices = []
            for idx, device in enumerate(devices):
                if device.get("max_input_channels", 0) > 0:
                    input_devices.append((idx, device))

            if not input_devices:
                raise RuntimeError("No microphone/input audio device detected.")

            default_input = sd.default.device[0] if sd.default.device else None
            if default_input is not None and default_input >= 0:
                for idx, _ in input_devices:
                    if idx == default_input:
                        self.input_device = idx
                        break

            if self.input_device is None:
                self.input_device = input_devices[0][0]

            if len(input_devices) > 1:
                device_names = ", ".join(
                    [f"{idx}:{dev['name']}" for idx, dev in input_devices]
                )
                logger.info(f"Multiple microphones found: {device_names}")

            selected_name = devices[self.input_device]["name"]
            logger.info(f"Selected microphone [{self.input_device}]: {selected_name}")

        except Exception as e:
            raise RuntimeError(f"Failed to select microphone: {e}") from e

    def record(self) -> np.ndarray:
        """
        Record audio for chunk_duration seconds.

        Returns:
            numpy.ndarray: Recorded mono audio samples
        """
        try:
            frames = int(self.sample_rate * self.chunk_duration)
            audio_data = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.input_device,
            )
            sd.wait()
            return audio_data.flatten()
        except Exception as e:
            raise RuntimeError(f"Audio recording failed: {e}") from e

    def save_wav(self, audio_data: np.ndarray, filename: str) -> None:
        """
        Save audio data to WAV file.

        Args:
            audio_data: Audio samples as numpy array
            filename: Output wav filename
        """
        try:
            audio_array = np.asarray(audio_data)
            if audio_array.dtype != np.int16:
                audio_array = np.clip(audio_array, -32768, 32767).astype(np.int16)

            with wave.open(filename, "wb") as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # int16 -> 2 bytes
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_array.tobytes())
        except Exception as e:
            raise RuntimeError(f"Failed to save WAV file '{filename}': {e}") from e

    def play_audio(self, filename: str) -> None:
        """
        Play WAV file using pygame mixer.

        Args:
            filename: Path to wav file
        """
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=self.sample_rate)
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(20)
        except Exception as e:
            raise RuntimeError(f"Failed to play audio '{filename}': {e}") from e

class VoiceAssistant:
    """
    Voice assistant for handling voice commands and responses.
    
    Attributes:
        language: Language code (e.g., 'en', 'or' for Odia)
        sample_rate: Audio sample rate in Hz
        chunk_duration: Duration of audio chunks in ms
        timeout_seconds: Timeout for listening
    """

    def __init__(
        self,
        language: str = "or",
        sample_rate: int = 16000,
        chunk_duration: int = 1024,
        timeout_seconds: int = 10,
    ) -> None:
        """
        Initialize the VoiceAssistant.
        
        Args:
            language: Language code for speech recognition and synthesis
            sample_rate: Sample rate for audio capture
            chunk_duration: Audio chunk size
            timeout_seconds: Listening timeout
        """
        self.language = language
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.timeout_seconds = timeout_seconds
        
        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init()
            logger.info("Pygame mixer initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize pygame mixer: {e}")
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=sample_rate)
        
        # Adjust for ambient noise
        with self.microphone as source:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            except Exception as e:
                logger.warning(f"Could not calibrate for ambient noise: {e}")
        
        self.is_listening = False
        self.intent_callbacks: Dict[str, Callable] = {}

    def listen(self) -> Optional[str]:
        """
        Listen to microphone input and convert to text.
        
        Returns:
            Recognized text or None if recognition failed
        """
        try:
            self.is_listening = True
            logger.info(f"Listening for {self.timeout_seconds} seconds...")
            
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.timeout_seconds,
                        phrase_time_limit=self.timeout_seconds
                    )
                except sr.WaitTimeoutError:
                    logger.warning("Listening timeout - no speech detected")
                    return None
            
            # Try Google Speech Recognition
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                logger.info(f"Recognized: {text}")
                return text
            except sr.UnknownValueError:
                logger.warning("Could not understand audio")
                return None
            except sr.RequestError as e:
                logger.error(f"Speech recognition error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in listen: {e}")
            return None
        finally:
            self.is_listening = False

    def process_intent(self, text: str) -> Dict[str, any]:
        """
        Process spoken text and extract intent.
        
        Args:
            text: Recognized speech text
            
        Returns:
            Dictionary with intent and confidence
        """
        try:
            text_lower = text.lower().strip()
            
            # Define intent patterns
            intents = {
                "greeting": [
                    r"hello", r"hi", r"hey", r"namaste",
                    r"how are you", r"good morning", r"good afternoon"
                ],
                "reminder": [
                    r"reminder", r"remind me", r"what\'?s next",
                    r"upcoming", r"next meeting", r"medication"
                ],
                "help": [
                    r"help", r"assist", r"support", r"what can you do",
                    r"instructions", r"guidance"
                ],
                "status": [
                    r"status", r"how am i", r"am i?.*well", r"check me"
                ],
                "emergency": [
                    r"emergency", r"danger", r"help", r"sos", r"urgent",
                    r"call.*help", r"doctor"
                ],
            }
            
            # Match intents
            matched_intent = None
            for intent, patterns in intents.items():
                for pattern in patterns:
                    if re.search(pattern, text_lower):
                        matched_intent = intent
                        break
                if matched_intent:
                    break
            
            result = {
                "text": text,
                "intent": matched_intent or "unknown",
                "confidence": 0.9 if matched_intent else 0.1,
            }
            
            logger.info(f"Intent processed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing intent: {e}")
            return {"text": text, "intent": "unknown", "confidence": 0.0}

    def speak(self, text: str, auto_play: bool = True) -> Optional[str]:
        """
        Convert text to speech and optionally play it.
        
        Args:
            text: Text to convert to speech
            auto_play: Whether to play audio immediately
            
        Returns:
            Path to audio file or None if failed
        """
        try:
            logger.info(f"Speaking: {text}")
            
            # Create audio file path
            audio_dir = Path("data/audio")
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_file = audio_dir / "response.mp3"
            
            # Generate speech
            tts = gTTS(text=text, lang=self.language, slow=False)
            tts.save(str(audio_file))
            
            if auto_play:
                try:
                    pygame.mixer.music.load(str(audio_file))
                    pygame.mixer.music.play()
                    # Wait for audio to finish playing
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)
                except Exception as e:
                    logger.error(f"Error playing audio with pygame: {e}")
            
            return str(audio_file)
            
        except Exception as e:
            logger.error(f"Error in speak: {e}")
            return None

    def register_intent_handler(self, intent: str, callback: Callable) -> None:
        """
        Register a callback for a specific intent.
        
        Args:
            intent: Intent name
            callback: Function to call when intent is detected
        """
        self.intent_callbacks[intent] = callback
        logger.info(f"Registered handler for intent: {intent}")

    def handle_intent(self, intent_result: Dict) -> any:
        """
        Execute handler for detected intent.
        
        Args:
            intent_result: Result from process_intent
            
        Returns:
            Result from handler or None
        """
        try:
            intent = intent_result.get("intent")
            callback = self.intent_callbacks.get(intent)
            
            if callback:
                return callback(intent_result)
            else:
                logger.warning(f"No handler for intent: {intent}")
                return None
                
        except Exception as e:
            logger.error(f"Error handling intent: {e}")
            return None

    def start_voice_loop(self) -> None:
        """
        Start continuous voice listening loop in a separate thread.
        """
        thread = threading.Thread(target=self._voice_loop, daemon=True)
        thread.start()
        logger.info("Voice loop started")

    def _voice_loop(self) -> None:
        """Main voice listening loop."""
        try:
            while True:
                text = self.listen()
                if text:
                    intent_result = self.process_intent(text)
                    self.handle_intent(intent_result)
        except Exception as e:
            logger.error(f"Error in voice loop: {e}")

    def stop_listening(self) -> None:
        """Stop the listening process."""
        self.is_listening = False
        logger.info("Listening stopped")
    
    def cleanup(self) -> None:
        """Cleanup resources and quit pygame mixer."""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                logger.info("Pygame mixer cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_status(self) -> Dict[str, any]:
        """
        Get current voice assistant status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "is_listening": self.is_listening,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "timeout_seconds": self.timeout_seconds,
        }
