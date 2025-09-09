"""
OpenAI adapter for v1.x SDK with PT-BR enforcement and resilience.
"""
import asyncio
import os
import time
from typing import Optional

import openai
from openai import OpenAI


class OpenAIClient:
    """
    Adapter for OpenAI v1.x SDK with PT-BR enforcement and error handling.
    """

    def __init__(
        self, api_key: Optional[str] = None, timeout_s: Optional[float] = None
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to env var OPENAI_API_KEY)
            timeout_s: Default timeout in seconds (defaults to env var OPENAI_TIMEOUT or 8s)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.default_timeout = timeout_s or float(os.getenv("OPENAI_TIMEOUT", "8"))

        # Initialize OpenAI client with timeout
        self.client = OpenAI(api_key=self.api_key, timeout=self.default_timeout)

    async def chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout_s: Optional[float] = None,
    ) -> str:
        """
        Send chat completion request to OpenAI.

        Args:
            model: Model to use (e.g., "gpt-3.5-turbo")
            system_prompt: System prompt (will be prefixed with PT-BR enforcement)
            user_prompt: User prompt
            temperature: Temperature for response generation (0-1)
            max_tokens: Maximum tokens in response
            timeout_s: Request timeout in seconds (overrides default)

        Returns:
            Response text in PT-BR (stripped and non-empty)
        """
        # Enforce PT-BR in system prompt
        ptbr_system = f"Responda estritamente em português do Brasil. {system_prompt}"

        # Build messages
        messages = [
            {"role": "system", "content": ptbr_system},
            {"role": "user", "content": user_prompt},
        ]

        # Log request
        timeout_val = timeout_s or self.default_timeout
        print(
            f"LLM|req|model={model}|temp={temperature}|max={max_tokens}|timeout={timeout_val}"
        )

        # Retry logic for rate limits and connection errors
        max_attempts = 3
        backoff_ms = [100, 300, 900]  # Exponential backoff

        for attempt in range(max_attempts):
            try:
                start_time = time.time()

                # Make request with custom timeout if provided
                if timeout_s:
                    # Create new client with custom timeout for this request
                    temp_client = OpenAI(api_key=self.api_key, timeout=timeout_s)
                    response = temp_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                # Extract response
                content = response.choices[0].message.content

                # Log success
                latency_ms = int((time.time() - start_time) * 1000)
                print(f"LLM|res|latency_ms={latency_ms}")

                # Sanitize and return
                return content.strip()

            except openai.BadRequestError as e:
                # 400 errors - don't retry
                print(f"LLM|error|type=BadRequestError|code=400|msg={str(e)}")
                return (
                    "Desculpe, houve um erro na requisição. Por favor, tente novamente."
                )

            except openai.RateLimitError as e:
                # 429 - retry with backoff
                print(
                    f"LLM|error|type=RateLimitError|code=429|msg={str(e)}|attempt={attempt + 1}"
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff_ms[attempt] / 1000.0)
                    continue
                return "Desculpe, o sistema está sobrecarregado. Por favor, aguarde um momento."

            except openai.APIConnectionError as e:
                # Connection error - retry
                print(
                    f"LLM|error|type=APIConnectionError|msg={str(e)}|attempt={attempt + 1}"
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff_ms[attempt] / 1000.0)
                    continue
                return "Desculpe, erro de conexão. Por favor, verifique sua internet."

            except openai.APITimeoutError:
                # Timeout - don't retry, return fallback
                print("LLM|error|type=APITimeoutError|msg=Request timed out")
                return (
                    "Desculpe, a requisição demorou muito. Por favor, tente novamente."
                )

            except openai.APIError as e:
                # Generic API error - retry for 5xx
                print(f"LLM|error|type=APIError|msg={str(e)}|attempt={attempt + 1}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff_ms[attempt] / 1000.0)
                    continue
                return (
                    "Desculpe, houve um erro no servidor. Por favor, tente mais tarde."
                )

            except Exception as e:
                # Unexpected error
                print(f"LLM|error|type=UnexpectedError|msg={str(e)}")
                return (
                    "Desculpe, ocorreu um erro inesperado. Por favor, tente novamente."
                )

        # Fallback if all retries exhausted
        return "Desculpe, não foi possível processar sua solicitação após várias tentativas."
