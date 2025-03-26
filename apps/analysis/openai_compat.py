"""
OpenAI Compatibility Module

This module provides a unified interface for working with different versions
of the OpenAI Python library (both v0.x and v1.x).
"""
import os
import logging
import json
import time
import traceback

logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    A compatibility wrapper for the OpenAI API that works with different
    versions of the openai Python library.
    """
    
    def __init__(self, api_key=None):
        """Initialize the client with the given API key."""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("No API key provided. Set OPENAI_API_KEY or pass api_key.")
        
        # We'll use the library in the simplest way to avoid compatibility issues
        self._setup_client()
    
    def _setup_client(self):
        """Set up the OpenAI client based on available library."""
        try:
            import openai
            self.openai = openai
            logger.info("OpenAI library imported successfully")
            
            # Just set the api_key at the module level - works with both versions
            openai.api_key = self.api_key
        except ImportError:
            logger.error("OpenAI library is not installed")
            raise ImportError("OpenAI library is not installed. Install it with 'pip install openai'.")
    
    def chat_completion(self, model, messages, temperature=0.7, max_tokens=None, **kwargs):
        """
        Create a chat completion using the appropriate API for the installed version.
        
        Args:
            model: The model to use (e.g., "gpt-4o", "gpt-3.5-turbo")
            messages: A list of message dictionaries with "role" and "content" keys
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API
            
        Returns:
            A standardized response dictionary
        """
        start_time = time.time()
        
        # Clean up and standardize parameters
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        # Add any other valid parameters
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value
        
        try:
            # Try v1.x API first (ChatCompletion doesn't exist in v1.x)
            if not hasattr(self.openai, 'ChatCompletion'):
                logger.info("Using v1.x OpenAI API (chat.completions.create)")
                try:
                    response = self.openai.chat.completions.create(**params)
                    
                    # Extract the necessary information from the object-based response
                    content = response.choices[0].message.content
                    tokens = {
                        "completion_tokens": response.usage.completion_tokens,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                    
                except Exception as e:
                    logger.error(f"Error with v1.x API: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
            else:
                # Use v0.x API
                logger.info("Using v0.x OpenAI API (ChatCompletion.create)")
                try:
                    response = self.openai.ChatCompletion.create(**params)
                    
                    # Extract the necessary information from the dictionary-based response
                    content = response['choices'][0]['message']['content']
                    tokens = {
                        "completion_tokens": response['usage']['completion_tokens'],
                        "prompt_tokens": response['usage']['prompt_tokens'],
                        "total_tokens": response['usage']['total_tokens']
                    }
                    
                except Exception as e:
                    logger.error(f"Error with v0.x API: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
            
            elapsed_time = time.time() - start_time
            
            # Return a standardized response
            return {
                "content": content,
                "tokens": tokens,
                "model": model,
                "elapsed_time": elapsed_time,
            }
            
        except Exception as e:
            logger.error(f"Error with OpenAI API: {str(e)}")
            logger.error(traceback.format_exc())
            
            # One final fallback attempt using a direct import
            try:
                logger.info("Trying final fallback with subprocess call")
                import subprocess
                import tempfile
                
                # Create a temporary script to call the API
                with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp:
                    temp.write(f"""
import os
import json
import openai

openai.api_key = "{self.api_key}"

try:
    # Try v1.x API first
    try:
        response = openai.chat.completions.create(
            model="{model}",
            messages={json.dumps(messages)},
            temperature={temperature},
            {f'max_tokens={max_tokens},' if max_tokens else ''}
        )
        print(json.dumps({{"v1": True, "content": response.choices[0].message.content, "tokens": {{"total_tokens": response.usage.total_tokens, "prompt_tokens": response.usage.prompt_tokens, "completion_tokens": response.usage.completion_tokens}}}}))
    except AttributeError:
        # Try v0.x API
        response = openai.ChatCompletion.create(
            model="{model}",
            messages={json.dumps(messages)},
            temperature={temperature},
            {f'max_tokens={max_tokens},' if max_tokens else ''}
        )
        print(json.dumps({{"v1": False, "content": response['choices'][0]['message']['content'], "tokens": {{"total_tokens": response['usage']['total_tokens'], "prompt_tokens": response['usage']['prompt_tokens'], "completion_tokens": response['usage']['completion_tokens']}}}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
""")
                
                # Run the script in a separate process
                temp_path = temp.name
                result = subprocess.check_output(['python', temp_path], text=True)
                os.unlink(temp_path)  # Clean up
                
                # Parse the JSON result
                result_json = json.loads(result)
                
                if "error" in result_json:
                    raise Exception(result_json["error"])
                
                elapsed_time = time.time() - start_time
                return {
                    "content": result_json["content"],
                    "tokens": result_json["tokens"],
                    "model": model,
                    "elapsed_time": elapsed_time,
                }
                
            except Exception as fallback_e:
                logger.error(f"Final fallback attempt failed: {str(fallback_e)}")
                raise e  # Raise the original error
            
    def calculate_cost(self, model, tokens):
        """
        Calculate the approximate cost of the API call.
        
        Args:
            model: The model used
            tokens: Dictionary with token counts
            
        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of early 2024)
        model_pricing = {
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4o": {"input": 0.01, "output": 0.03}
        }
        
        if model in model_pricing:
            input_cost = (tokens["prompt_tokens"] / 1000000) * model_pricing[model]["input"]
            output_cost = (tokens["completion_tokens"] / 1000000) * model_pricing[model]["output"]
            return input_cost + output_cost
        
        # Default cost estimation if model not in our pricing table
        return (tokens["total_tokens"] / 1000000) * 0.02  # Conservative estimate