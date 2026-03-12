import time
from modules.voice import VoiceAssistant

def voice_pipeline():
    assistant = VoiceAssistant(language="or", timeout_seconds=8)

    intent_responses = {
        "emergency": "Help is coming. ସାହାଯ୍ୟ ଆସୁଛି.",
        "medicine_query": "Your medicine time is scheduled. ଔଷଧ ସମୟ ହୋଇଛି.",
        "greeting": "Hello! How can I help? ନମସ୍କାର!",
        "unknown": "I did not understand. Please repeat. ଦୟାକରି ପୁନରାବୃତ୍ତି କରନ୍ତୁ.",
    }

    try:
        while True:
            print("\nListening...")
            
            # 1. Listen and transcribe
            start_time = time.time()
            transcribed_text = assistant.listen()
            transcription_time = time.time() - start_time

            if transcribed_text:
                print(f"Transcription: \033[32m{transcribed_text}\033[0m [Took {transcription_time:.2f}s]")

                # 2. Classify intent
                start_time = time.time()
                intent_result = assistant.process_intent(transcribed_text)
                intent = intent_result.get("intent", "unknown")
                intent_confidence = float(intent_result.get("confidence", 0.0))
                classification_time = time.time() - start_time
                print(f"Intent: \033[33m{intent}\033[0m (Confidence: {intent_confidence:.2f}) [Took {classification_time:.2f}s]")

                # 3. Generate and speak response
                response_text = intent_responses.get(intent, intent_responses["unknown"])
                
                start_time = time.time()
                assistant.speak(response_text)
                tts_time = time.time() - start_time
                print(f"Response: \033[34m{response_text}\033[0m [Took {tts_time:.2f}s]")

            else:
                print("Transcription failed. No intent processed.")

    except KeyboardInterrupt:
        print("\n\nExiting voice pipeline. Goodbye!")
    finally:
        assistant.cleanup()

if __name__ == "__main__":
    print("--- Voice Pipeline Test ---")
    voice_pipeline()