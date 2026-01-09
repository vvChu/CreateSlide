import os
from google import genai
from dotenv import load_dotenv

# Try to load env
load_dotenv()

def list_available_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in environment.")
        return

    print(f"Checking available models with API Key: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        client = genai.Client(api_key=api_key)
        
        print("\n--- Querying client.models.list() ---")
        # Note: The V2 SDK might use different pagination or accessors. 
        # Using standard iteration.
        count = 0
        for model in client.models.list():
            # Debug: Check attributes
            # print(dir(model)) 
            # In V2 SDK, it might be 'supportedGenerationMethods' (camelCase) or just check name
            print(f"FOUND: {model.name}")
            count += 1
        
        if count == 0:
            print("WARNING: No models found with 'generateContent' capability.")
            
    except Exception as e:
        print(f"CRASH during list_models: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_available_models()
