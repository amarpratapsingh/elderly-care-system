"""
Speech-to-Text test script.

Workflow:
1. Record 5 seconds of audio from microphone
2. Save to test_input.wav
3. Calibrate energy threshold for ambient noise
4. Transcribe with Google SpeechRecognition API (English)
5. Print transcription or graceful error message
"""

import speech_recognition as sr

from modules.voice import AudioHandler


def main() -> None:
    output_file = "test_input.wav"
    recognizer = sr.Recognizer()

    try:
        print("Initializing audio handler...")
        audio_handler = AudioHandler(sample_rate=16000, chunk_duration=5)
    except Exception as e:
        print(f"Could not initialize microphone: {e}")
        return

    try:
        print("Calibrating ambient noise (1 second)...")
        try:
            with sr.Microphone(sample_rate=16000) as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                recognizer.dynamic_energy_threshold = True
                print(f"Energy threshold set to: {recognizer.energy_threshold:.2f}")
        except Exception as e:
            print(f"Ambient noise calibration skipped: {e}")

        print("Recording 5 seconds of audio... Speak now.")
        audio_data = audio_handler.record()
        audio_handler.save_wav(audio_data, output_file)
        print(f"Audio saved to {output_file}")

        with sr.AudioFile(output_file) as source:
            recorded_audio = recognizer.record(source)

        print("Transcribing with Google Speech API...")
        text = recognizer.recognize_google(recorded_audio, language="en-US")
        print(f"Transcribed text: {text}")

    except sr.UnknownValueError:
        print("Could not understand the recorded audio.")
    except sr.RequestError as e:
        print(f"Speech recognition service error: {e}")
    except RuntimeError as e:
        print(f"Audio error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
