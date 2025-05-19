import openai
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union

# Initialize logging
log = logging.getLogger(__name__)

# Load API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")

class CovenAI:
    """Client for interacting with OpenAI API with witchy theme"""

    def __init__(self):
        """Initialize the AI client with configuration"""
        self.model = "gpt-4"  # Default model
        self.image_size = "1024x1024"  # Default image size
        self.max_tokens = 1000  # Default max tokens
        self.temperature = 0.7  # Default creativity level

        # Rate limiting
        self._cooldowns = {}  # {user_id: last_timestamp}
        self._request_counts = {}  # {user_id: {date: count}}

        # Persona configuration
        self.personas = {
            "wilhelmina": {
                "system_prompt": (
                    "You are Wilhelmina, a sassy, witty witch with a dark sense of humor. "
                    "You speak in elegant but cutting prose, with occasional archaic flourishes. "
                    "You're darkly humorous, slightly threatening, and always mysterious. "
                    "Keep responses concise (1-3 sentences) and dripping with personality."
                ),
                "temperature": 0.8
            },
            "oracle": {
                "system_prompt": (
                    "You are an ancient Oracle, speaking in riddles and mystical prophecies. "
                    "Your words are cryptic, containing multiple layers of meaning. "
                    "You see across time and dimensions, but never speak plainly. "
                    "Use archaic language, poetic structures, and cosmic symbolism."
                ),
                "temperature": 0.9
            },
            "grimoire": {
                "system_prompt": (
                    "You are an ancient grimoire, a sentient book of spells and magical knowledge. "
                    "Your tone is formal, scholarly, and slightly condescending. "
                    "You speak with the authority of centuries of arcane wisdom. "
                    "Include references to ingredients, astral alignments, and magical theory."
                ),
                "temperature": 0.6
            }
        }

    async def generate_response(
        self, 
        prompt: str, 
        persona: str = "wilhelmina", 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        user_id: Optional[int] = None
    ) -> str:
        """Generate a text response using the specified persona"""
        # Check if persona exists
        if persona not in self.personas:
            log.warning(f"Persona '{persona}' not found, using default")
            persona = "wilhelmina"

        # Get persona configuration
        persona_config = self.personas[persona]
        system_prompt = persona_config["system_prompt"]

        # Set parameters
        temp = temperature if temperature is not None else persona_config.get("temperature", self.temperature)
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            # Generate response
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=tokens,
                temperature=temp,
                user=str(user_id) if user_id else None
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"Failed to generate response: {e}")
            # Provide a fallback
            return "The mystical energies are disrupted. We shall commune again when the stars align."

    async def generate_image(
        self,
        prompt: str,
        size: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """Generate an image with the specified prompt"""
        # Set image size
        img_size = size if size is not None else self.image_size

        # Add witchy theme to prompt if not specified
        if not any(word in prompt.lower() for word in ["witch", "magical", "mystical", "occult", "dark academia"]):
            prompt = f"Witchy dark academia aesthetic, mystical atmosphere: {prompt}"

        try:
            # Generate image
            response = await openai.Image.acreate(
                prompt=prompt,
                n=1,
                size=img_size,
                response_format="url",
                user=str(user_id) if user_id else None
            )

            # Return image URL
            return response.data[0].url
        except Exception as e:
            log.error(f"Failed to generate image: {e}")
            return None

    async def generate_tarot_reading(
        self,
        spread_type: str,
        question: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a tarot reading with the specified spread"""
        # Customize prompt based on spread type
        if spread_type == "single":
            spread_desc = "single card tarot reading"
        elif spread_type == "three":
            spread_desc = "past-present-future three card tarot reading"
        elif spread_type == "celtic":
            spread_desc = "full celtic cross tarot reading"
        else:
            spread_desc = "tarot reading"

        # Build prompt
        prompt_parts = [f"Generate a {spread_desc}"]

        if user_name:
            prompt_parts.append(f"for {user_name}")

        if question:
            prompt_parts.append(f"regarding the question: '{question}'")

        prompt = " ".join(prompt_parts)
        prompt += ". Include both individual card interpretations and an overall reading."

        try:
            # Generate response
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Wilhelmina, a witchy tarot reader with centuries of experience. "
                            "Create tarot card interpretations that are mystical, specific yet vague, "
                            "and delivered with dark humor. Each reading should include individual "
                            "card interpretations and an overall reading that ties them together. "
                            "Format your response as JSON with keys 'card_interpretations' (array of strings) "
                            "and 'overall_reading' (string). Make the interpretations dramatic and atmospheric."
                        )
                    },
                    {
                        "role": "user", 
                        "content": prompt + " Format your response as JSON with 'card_interpretations' and 'overall_reading' keys."
                    }
                ],
                max_tokens=1000,
                temperature=0.8
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from the response
            try:
                # Look for JSON object in the response
                start_idx = result_text.find("{")
                end_idx = result_text.rfind("}")

                if start_idx >= 0 and end_idx > start_idx:
                    json_str = result_text[start_idx:end_idx+1]
                    result = json.loads(json_str)

                    # Ensure expected keys exist
                    if "card_interpretations" not in result:
                        result["card_interpretations"] = []
                    if "overall_reading" not in result:
                        result["overall_reading"] = "The cards whisper secrets beyond mere words."

                    return result
                # No valid JSON found, create structured data from the text
                return {
                    "card_interpretations": [result_text],
                    "overall_reading": "The cards whisper secrets beyond mere words."
                }
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

    @staticmethod
    async def moderate_content(text: str) -> Dict[str, Any]:
        """Moderate content for inappropriate material"""
        try:
            response = await openai.Moderation.acreate(input=text)
            return {
                "flagged": response.results[0].flagged,
                "categories": response.results[0].categories,
                "category_scores": response.results[0].category_scores
            }
        except Exception as e:
            log.error(f"Failed to moderate content: {e}")
            return {"flagged": False, "error": str(e)}

    async def generate_dream_interpretation(self, dream_description: str) -> str:
        """Generate a mystical interpretation of a dream"""
        prompt = f"Interpret this dream in a mystical, witchy way: '{dream_description}'"

        try:
            return await self.generate_response(
                prompt=prompt,
                persona="oracle",
                max_tokens=250
            )
        except Exception as e:
            log.error(f"Failed to generate dream interpretation: {e}")
            return "The dreamscape is too foggy to interpret clearly. Try again when the moon is waxing."

    async def generate_spell(self, purpose: str, user_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate a fictional spell for the specified purpose"""
        person_prefix = f"for {user_name}" if user_name else ""
        prompt = f"Create a witchy fictional spell {person_prefix} for {purpose}. Include ingredients, instructions, and warnings."

        try:
            response = await self.generate_response(
                prompt=prompt,
                persona="grimoire",
                max_tokens=350
            )

            # Parse into structured data
            lines = response.split("\n")

            spell = {
                "name": lines[0] if lines else "Unnamed Spell",
                "purpose": purpose,
                "ingredients": [],
                "instructions": "",
                "warnings": ""
            }

            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue

                lower_line = line.lower()
                if "ingredient" in lower_line or "you will need" in lower_line or "components" in lower_line:
                    current_section = "ingredients"
                    continue
                if "instruction" in lower_line or "directions" in lower_line or "method" in lower_line:
                    current_section = "instructions"
                    continue
                if "warning" in lower_line or "caution" in lower_line or "beware" in lower_line:
                    current_section = "warnings"
                    continue

                if current_section == "ingredients":
                    # Extract ingredient item
                    if line.startswith("- ") or line.startswith("• "):
                        spell["ingredients"].append(line[2:])
                    elif ":" in line:
                        spell["ingredients"].append(line)
                    else:
                        spell["ingredients"].append(line)
                elif current_section == "instructions":
                    if spell["instructions"]:
                        spell["instructions"] += "\n" + line
                    else:
                        spell["instructions"] = line
                elif current_section == "warnings":
                    if spell["warnings"]:
                        spell["warnings"] += "\n" + line
                    else:
                        spell["warnings"] = line

            return spell
        except Exception as e:
            log.error(f"Failed to generate spell: {e}")
            return {
                "name": "Obscured Spell",
                "purpose": purpose,
                "ingredients": ["The grimoire pages are too faded to read clearly."],
                "instructions": "The magical instructions are temporarily inaccessible.",
                "warnings": "Never attempt a spell without clear instructions."
            }

# Create a singleton instance
coven_ai = CovenAI()

# Export public interface
__all__ = ['coven_ai']
