import time
from modules.voice import SpeechRecognizer

def test_odia_transcription():
    recognizer = SpeechRecognizer(language=\or-IN\)
    
    test_phrases = ["ନମସ୍କାର", "ସାହାଯ୍ୟ କର", "ଧନ୍ୟବାଦ"]
    
    for phrase in test_phrases:
        print(f"\nPlease say in Odia: '{phrase}'")
        
        # Record and transcribe
        transcribed_text, confidence = recognizer.transcribe_from_mic(duration=3)
        
        if transcribed_text:
            print(f"You said: {transcribed_text} (Confidence: {confidence:.2f})")
            
            # Simple check
            if phrase in transcribed_text:
                print("Result: Correctly recognized!")
            else:
                print("Result: Recognition mismatch.")
        else:
            print("Result: Transcription failed. Please try again.")
        
        # Pause before next phrase
        time.sleep(2)

if __name__ == "__main__":
    print("--- Odia Speech-to-Text Test ---")
    test_odia_transcription()
    print("\n--- Test Complete ---")