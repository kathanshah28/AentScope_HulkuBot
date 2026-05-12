import requests
import json
import google.generativeai as genai
from groq import Groq
import os

# Import all prompts from your prompts.py file
from stsrc.prompts import (
    SYSTEM_PROMPT_ROUTER,
    SYSTEM_PROMPT_MOVEMENT,
    SYSTEM_PROMPT_CLEANER,
    SYSTEM_PROMPT_CUBE_SPAWNER
)

def generate_ros_code(user_prompt: str, model_name: str = "deepseek-coder:6.7b", provider: str = "ollama", api_key: str = None, prompt_type: str = "MOVEMENT") -> str:
    """
    Sends a prompt to the selected LLM provider.
    
    Args:
        prompt_type (str): "ROUTER", "MOVEMENT", or "CLEANER". 
                           Selects the corresponding system prompt from prompts.py.
    """
    
    # --- 1. Select the Correct System Prompt ---
    if prompt_type == "ROUTER":
        system_instruction = SYSTEM_PROMPT_ROUTER
    elif prompt_type == "CLEANER":
        system_instruction = SYSTEM_PROMPT_CLEANER
    elif prompt_type == "SPAWNER":
        system_instruction = SYSTEM_PROMPT_CUBE_SPAWNER
    else:
        # Default to MOVEMENT if unknown or explicitly requested
        system_instruction = SYSTEM_PROMPT_MOVEMENT

    # --- 2. Call the Provider ---
    if provider == "gemini":
        return _generate_with_gemini(user_prompt, model_name, api_key, system_instruction)
    elif provider == "groq":
        return _generate_with_groq(user_prompt, model_name, api_key, system_instruction)
    else:
        return _generate_with_ollama(user_prompt, model_name, system_instruction)

# ---------------------------------------------------------------------------
# PROVIDER IMPLEMENTATIONS (Updated to accept system_instruction)
# ---------------------------------------------------------------------------

def _generate_with_groq(user_prompt: str, model_name: str, api_key: str, system_instruction: str) -> str:
    if not api_key:
        return "Error: Groq API Key is required."
    try:
        client = Groq(api_key=api_key)
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]
        
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=model_name,
            temperature=0.1,
        )
        
        generated_text = chat_completion.choices[0].message.content
        return _clean_and_validate_json(generated_text)
        
    except Exception as e:
        return f"Error talking to Groq: {str(e)}"

def _generate_with_gemini(user_prompt: str, model_name: str, api_key: str, system_instruction: str) -> str:
    if not api_key:
        return "Error: Gemini API Key is required."
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # Gemini works best when system prompt is prepended contextually or via specific API fields
        # Here we prepend it for simplicity and robustness across versions
        full_prompt = f"{system_instruction}\n\nUser Request: {user_prompt}\n\nResponse:"
        
        response = model.generate_content(full_prompt)
        return _clean_and_validate_json(response.text)
        
    except Exception as e:
         return f"Error talking to Gemini: {str(e)}"

def _generate_with_ollama(user_prompt: str, model_name: str, system_instruction: str) -> str:
    url = "http://localhost:11434/api/generate"
    
    # Construct prompt manually as many Ollama models handle system prompts differently
    full_prompt = f"{system_instruction}\n\nUser Request: {user_prompt}\n\nResponse:"
    
    payload = {
        "model": model_name,
        "prompt": full_prompt,
        "stream": False, 
        "options": {
            "temperature": 0.1,
            "stop": ["User Request:", "Request:"] 
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return _clean_and_validate_json(result.get("response", ""))
        
    except Exception as e:
        return f"Error talking to Ollama: {str(e)}"

def _clean_and_validate_json(generated_text: str) -> str:
    # Remove Markdown code blocks
    clean_code = generated_text.strip()
    if clean_code.startswith("```json"):
        clean_code = clean_code.replace("```json", "", 1)
    elif clean_code.startswith("```"):
        clean_code = clean_code.replace("```", "", 1)
    if clean_code.endswith("```"):
        clean_code = clean_code.rsplit("```", 1)[0]
        
    # Validation
    try:
        parsed_json = json.loads(clean_code)
        return json.dumps(parsed_json, indent=2)
    except json.JSONDecodeError:
        return f"Error: Model did not return valid JSON. Raw output:\n{clean_code}"