import json
import os
from typing import Dict, Any, List, Optional, Union
import logging
import random
from openai import OpenAI

# Initialize logging
log = logging.getLogger(__name__)

# Load API key from environment and initialize client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Store user context for more personalized responses
user_contexts = {}

async def generate_wilhelmina_reply(prompt: str, user_id: Optional[int] = None) -> str:
    """Generate a witchy, sassy reply using OpenAI"""
    try:
        # Add user-specific context if available
        context = ""
        if user_id and user_id in user_contexts:
            context = user_contexts[user_id].get("personality_notes", "")

        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": (
                    "You are Wilhelmina, a centuries-old witch with limitless sarcasm and sass. "
                    "You speak with elegant, cutting wit and occasional archaic language that reveals your age. "
                    "Your humor is dark but never cruel, your observations sharp but never mean-spirited. "
                    "You're mysterious, slightly intimidating, but secretly protective of your coven members. "
                    f"Keep responses concise (1-3 sentences) and rich with personality. {context}"
                )
            }, {
                "role": "user",
                "content": prompt
            }]
        )

        # Get content from response
        if response and response.choices and response.choices[0].message:
            reply = response.choices[0].message.content
            if reply:
                reply = reply.strip()
            else:
                reply = "The mystical energies are confounding me today."
        else:
            reply = "The veil between realms is particularly thick today."

        # Store something interesting about the user for future interactions
        if user_id and "compliment" in prompt.lower() or "roast" in prompt.lower():
            if user_id not in user_contexts:
                user_contexts[user_id] = {}

            # Limit to 10 contexts per user to prevent memory bloat
            if len(user_contexts) > 500:
                oldest_user = min(user_contexts.keys(), key=lambda k: user_contexts[k].get("last_update", 0))
                del user_contexts[oldest_user]

            # Update context with something to remember about this user
            import time
            user_contexts[user_id]["last_update"] = time.time()

            # No need to make another API call here, just use what we already know

        return reply
    except Exception as e:
        log.error(f"Failed to generate OpenAI response: {e}")
        # Provide a fallback response if API fails
        fallback_responses = [
            "The crystal ball is cloudy today, darling. Try again when the stars align.",
            "My powers are temporarily bound by forces beyond my control. How... inconvenient.",
            "The spirits are being uncooperative. Much like your fashion choices.",
            "I sense a disturbance in the arcane networks. We shall speak again soon.",
            "Even a witch's power has its limits. Especially when the API goblins interfere.",
            "The cosmic signals are scrambled. Mercury must be in retrograde... again.",
            "My familiars are on strike. Union negotiations, you understand.",
            "The elder gods have temporarily suspended my account. Bureaucracy, darling."
        ]
        return random.choice(fallback_responses)

async def generate_tarot_reading(prompt: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Generate a tarot reading with card interpretations"""
    try:
        # Add user-specific context if available
        context = ""
        if user_id and user_id in user_contexts:
            context = user_contexts[user_id].get("personality_notes", "")

        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{
                "role": "system",
                "content": (
                    "You are Wilhelmina, a witchy tarot reader with centuries of experience. "
                    "Create tarot card interpretations that are mystical, specific yet vague, "
                    "and delivered with dark humor and personality. Each reading should include individual "
                    "card interpretations and an overall reading that ties them together. "
                    f"Make the interpretations dramatic, atmospheric, and personalized. {context}"
                    "You MUST format your response as JSON with keys 'card_interpretations' (array of strings) "
                    "and 'overall_reading' (string)."
                )
            }, {
                "role": "user",
                "content": prompt
            }]
        )

        # Get content from response
        result_text = ""
        if response and response.choices and response.choices[0].message:
            content = response.choices[0].message.content
            if content:
                result_text = content.strip()
            else:
                result_text = "{}"
        else:
            result_text = "{}"

        # Parse JSON directly since we used response_format={"type": "json_object"}
        try:
            result = json.loads(result_text)

            # Ensure expected keys exist
            if "card_interpretations" not in result:
                result["card_interpretations"] = []
            if "overall_reading" not in result:
                result["overall_reading"] = "The cards whisper secrets beyond mere words."

            return result
        except json.JSONDecodeError:
            # If JSON parsing fails, create structured data from the text
            return {
                "card_interpretations": [result_text],
                "overall_reading": "The cards reveal mysteries shrouded in mist."
            }
    except Exception as e:
        log.error(f"Failed to generate tarot reading: {e}")
        # Provide a fallback response if API fails
        return {
            "card_interpretations": [
                "The cards are mysteriously silent today. Perhaps some cosmic interference."
            ],
            "overall_reading": "The veil between worlds is too thick at the moment."
        }

async def generate_image(prompt: str, style: Optional[str] = "witchy dark academia") -> Optional[str]:
    """Generate an image using DALL-E based on the prompt"""
    try:
        # Sanitize and enhance prompt
        enhanced_prompt = f"{style} style: {prompt}"

        # Generate image
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            n=1,
            size="1024x1024"
        )

        # Return image URL
        if response and response.data and len(response.data) > 0:
            return response.data[0].url
        log.error("Empty response from image generation API")
        return None
    except Exception as e:
        log.error(f"Failed to generate image: {e}")
        return None

# Export public functions
__all__ = ['generate_wilhelmina_reply', 'generate_tarot_reading', 'generate_image']
