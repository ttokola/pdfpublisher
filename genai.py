import sys
import os
import json
import time
from google import genai as google_genai

# --- CONFIGURATION ---
AI_LIST = ["Google"]

def getAI(AI, api_key, model, timeout=30, maxperminute=15):
    """Factory function to return the correct AI instance."""
    if AI not in AI_LIST:
        print(f"[ERROR] AI '{AI}' is not on the list")
        sys.exit(1)
    
    if AI == "Google":
        return GoogleAI(api_key=api_key, model=model, timeout=timeout, maxperminute=maxperminute)
    # Copypaste and implement for other AI's


# --- Parent Class ---
class AIwrapper:
    def __init__(self, api_key, model, timeout, maxperminute):
        self.api_key = api_key
        self.model = model
        self.timeout = int(timeout)
        self.maxperminute = int(maxperminute)
        self.last_call_time = 0

    def _throttle(self):
        """Simple rate limiting based on maxperminute."""
        interval = 60.0 / self.maxperminute
        elapsed = time.time() - self.last_call_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self.last_call_time = time.time()

                    
    def translate(self, to_translate, course_prompt, source_lang, target_lang):
        """Builds the prompt and handles the translation logic."""

        # Using structured prompts
        translate_prompt = (
            f"You are a professional translator for our university course content internationalisation project. I need a translations for my course material. {course_prompt}. "
            f"The input is a list of [fingerprint, original_text, empty_translation_slot]. Fill the third column (the empty string) with the translation from {source_lang} to {target_lang}. Do not modify the fingerprints or the original text. Return only the valid JSON array."
            f"Preserve all Markdown formatting including bold, italics, and links and additionally remember to retain line breaks."
            f"Return ONLY the JSON array, with the translations filled in!\n\nJSON ARRAY TO FILL WITH THE TRANSLATIONS:\n\n"
        )
        
        # Call the subclass implementation of prompt(), if there is enough to translate
        # Store results to log 
        # We pass texts as content parts to keep the prompt clean
        textcount = len(to_translate)
        with open("ai_responses.log", "a", encoding="utf-8") as logfile:
            logfile.write("***************************************************\n")
            logfile.write(f"{translate_prompt}")
            json_input = json.dumps(to_translate, ensure_ascii=False, indent=2)
            logfile.write(f"{json_input}")
            logfile.write("***************************************************\n")
            ai_response = self.prompt(translate_prompt, to_translate)
            logfile.write("--------------------\n")
            logfile.write(f"{ai_response}")
            logfile.write("\n--------------------\n")
            logfile.close()
        return ai_response

# --- Google Implementation ---
class GoogleAI(AIwrapper):
    def __init__(self, api_key, model, timeout, maxperminute):
        # Initialize the Parent
        super().__init__(api_key, model, timeout, maxperminute)
        
        # Setup Google Client
        try:
            self.client = google_genai.Client(api_key=self.api_key)
            # Minimal connectivity test
            #self.client.models.generate_content(
            #    model=self.model, 
            #    contents="ping", 
            #    config={"max_output_tokens": 1}
            #)
        except Exception as e:
            print(f"[ERROR] Failed to connect to Google AI: {e}")
            sys.exit(1)

    def prompt(self, system_instruction, request_data, max_retries=5):
        """Google-specific implementation using explicit API retry hints."""

        # 1. Prepare the mirrored input structure
        # We turn the list into a JSON string so the AI sees it as a single 'object' to translate
        size = len(request_data)
        json_input = json.dumps(request_data, ensure_ascii=False)

        full_prompt = f"{system_instruction}{json_input}"   
        #print(f"Full prompt is: {full_prompt}")

        strict_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "text": {"type": "STRING"},
                    "translation": {"type": "STRING"}
                },
                "required": ["id", "text", "translation"]
            }
        }

        #sys.stdout.flush()
        for attempt in range(max_retries):
            self._throttle()
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": strict_schema
                    }
                )
            
                if response.parsed is not None:
                    return response.parsed
                if response.text:
                    try:
                        return json.loads(response.text)
                    except json.JSONDecodeError:
                        print(f"[ERROR] AI returned non-JSON text: {response.text}")
                        return []
                print(f"[WARN] AI returned an empty response. Check safety filters or prompt.")
                return []
            except Exception as e:
                # Check if this is a rate limit error (429)
                # The SDK error object usually contains the 'details' from the server
                if hasattr(e, 'details'):
                    # Look for RetryInfo in the error details list
                    retry_info = next((d for d in e.details if 'retryDelay' in str(d)), None)
                    if retry_info:
                        # retry_info is usually a string or dict containing '43s' or '43.76s'
                        # We extract the digits and convert to float
                        import re
                        delay_str = str(retry_info)
                        match = re.search(r"(\d+\.?\d*)s", delay_str)
                        if match:
                            wait_seconds = float(match.group(1)) + 1.0 # +1s buffer for safety
                            print(f"[QUOTA] API requested wait: {wait_seconds}s. Sleeping...")
                            time.sleep(wait_seconds)
                            continue # Retry the loop

                # Fallback if no explicit retry info is found but it's a 429
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = 60 # Default to 1 min if we can't parse the specific delay
                    print(f"[QUOTA] Rate limit hit. No specific delay found, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                # If it's a different error (e.g. 400 Bad Request), don't retry
                print(f"[ERROR] Google API Call failed: {e}")
                break
        return []
        
