import time
from modules.voice import VoiceAssistant

def test_odia_transcription():
    assistant = VoiceAssistant(language="or", timeout_seconds=5)
    
    test_phrases = ["ନମସ୍କାର", "ସାହାଯ୍ୟ କର", "ଧନ୍ୟବାଦ"]

    try:
        for phrase in test_phrases:
            print(f"\nPlease say in Odia: '{phrase}'")

            transcribed_text = assistant.listen()

            if transcribed_text:
                intent_result = assistant.process_intent(transcribed_text)
                confidence = float(intent_result.get("confidence", 0.0))
                print(f"You said: {transcribed_text} (Confidence: {confidence:.2f})")

                if phrase in transcribed_text:
                    print("Result: Correctly recognized!")
                else:
                    print("Result: Recognition mismatch.")
            else:
                print("Result: Transcription failed. Please try again.")

            time.sleep(2)
    finally:
        assistant.cleanup()

if __name__ == "__main__":
    print("--- Odia Speech-to-Text Test ---")
    test_odia_transcription()
    print("\n--- Test Complete ---")