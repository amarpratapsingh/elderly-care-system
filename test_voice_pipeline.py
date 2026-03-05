import time
from modules.voice import SpeechRecognizer, IntentClassifier, TTSEngine

def voice_pipeline():
    recognizer = SpeechRecognizer(language='or-IN')
    classifier = IntentClassifier()
    tts_engine = TTSEngine(language='or')

    intent_responses = {
        'emergency': "Help is coming. ସାହାଯ୍ୟ ଆସୁଛି.",
        'medicine_query': "Your medicine time is scheduled. ଔଷଧ ସମୟ ହୋଇଛି.",
        'greeting': "Hello! How can I help? ନମସ୍କାର!",
        'unknown': "I did not understand. Please repeat. ଦୟାକରି ପୁନରାବୃତ୍ତି କରନ୍ତୁ."
    }

    try:
        while True:
            print("\nListening...")
            
            # 1. Record and Transcribe
            start_time = time.time()
            transcribed_text, confidence = recognizer.transcribe_from_mic(duration=3)
            transcription_time = time.time() - start_time

            if transcribed_text:
                print(f"Transcription: \033[32m{transcribed_text}\033[0m (Confidence: {confidence:.2f}) [Took {transcription_time:.2f}s]")

                # 2. Classify Intent
                start_time = time.time()
                intent, intent_confidence, _ = classifier.classify(transcribed_text)
                classification_time = time.time() - start_time
                print(f"Intent: \033[33m{intent}\033[0m (Confidence: {intent_confidence:.2f}) [Took {classification_time:.2f}s]")

                # 3. Generate and Speak Response
                response_text = intent_responses.get(intent, intent_responses['unknown'])
                
                start_time = time.time()
                tts_engine.speak(response_text)
                tts_time = time.time() - start_time
                print(f"Response: \033[34m{response_text}\033[0m [Took {tts_time:.2f}s]")

            else:
                print("Transcription failed. No intent processed.")

    except KeyboardInterrupt:
        print("\n\nExiting voice pipeline. Goodbye!")

if __name__ == "__main__":
    print("--- Voice Pipeline Test ---")
    voice_pipeline()