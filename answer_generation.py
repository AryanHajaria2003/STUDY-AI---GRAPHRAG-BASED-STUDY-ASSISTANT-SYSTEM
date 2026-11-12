
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# LOAD ENVIRONMENT VARIABLES
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY is missing. Check the .env file."
    )

client = Groq(api_key=api_key)


# PREPARE RETRIEVED GRAPH CONTEXT
def prepare_context(data, max_chars=12000):
    lines = [f"Subject: {data['subject']}"]
    remaining = max_chars
    seen_chunks = set()

    for unit, details in data["units"].items():
        header = f"\n{unit}: {details.get('title') or ''}"

        if len(header) > remaining:
            break

        lines.append(header)
        remaining -= len(header)

        for topic in details["topics"]:
            topic_line = (
                f"\nTopic: {topic['name']}"
                f"\nConcepts: {', '.join(topic['concepts'])}"
            )

            if len(topic_line) > remaining:
                break

            lines.append(topic_line)
            remaining -= len(topic_line)

            for chunk in topic["chunks"]:
                text = chunk.get("text", "").strip()

                if not text or text in seen_chunks:
                    continue

                seen_chunks.add(text)

                source = f"\nSource: {text[:800]}"

                if len(source) > remaining:
                    break

                lines.append(source)
                remaining -= len(source)

            if remaining <= 0:
                break

        if remaining <= 0:
            break

    return "\n".join(lines)


# GENERATE STUDY PLAN
def generate_study_plan(data):
    if not data or not data.get("units"):
        return "No subject data was retrieved."

    context = prepare_context(data)

    prompt = f"""
You are a syllabus-based study assistant.

Generate exactly these three sections:

1. Suggested Prerequisites
2. Learning Roadmap
3. Important Topics

Rules:
- Use the retrieved syllabus as your primary source.
- Do not invent syllabus topics or units.
- Label inferred prerequisites as suggestions.
- Arrange topics in a logical learning sequence.
- Prioritize important topics based on syllabus coverage.
- Do not explain individual topics.
- Keep the response clear and concise.

Retrieved syllabus:
{context}
"""

    response = client.chat.completions.create(
        model=os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b"
        ),
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=1500
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    print("Answer generation module loaded successfully.")
