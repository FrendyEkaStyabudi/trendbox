# backend/services/nlp_service.py
import requests
import re
from config import Settings


def _known_count_query(prompt: str):
    """Handle common count intents without relying on the LLM to compose SQL."""
    normalized = re.sub(r"\s+", " ", prompt.lower()).strip()
    asks_for_count = any(word in normalized for word in ("berapa", "jumlah", "total", "count"))
    asks_for_today = any(phrase in normalized for phrase in ("hari ini", "today", "sekarang"))

    if not (asks_for_count and asks_for_today):
        return None

    if any(word in normalized for word in ("pakaian", "baju", "clothing", "shorts", "outer", "skirt", "t-shirt")):
        table = "clothing_track"
        subject = "clothing data"
    elif any(word in normalized for word in ("kepala", "head", "headwear", "hijab", "topi", "hat", "rambut")):
        table = "head_track"
        subject = "head attribute data"
    else:
        # One tracked person/session can be represented in all three tables. For
        # a generic count, emotion_track is the canonical event table so records
        # are not counted three times.
        table = "emotion_track"
        subject = "detection data"

    sql = f"SELECT COUNT(*) AS total_data FROM {table} WHERE DATE(timestamp) = CURDATE();"
    reason = f"Counts today's {subject} from the {table} table."
    return sql, reason

# (Fungsi _parse_sql_and_reason dan _generate_sql_from_endpoint tetap sama persis seperti sebelumnya)
def _parse_sql_and_reason(model_output_text: str):
    # ... (Tidak ada perubahan di sini)
    sql_query = ""
    reasoning = "No specific reasoning was found, or the model output format was invalid."
    cleaned_output = model_output_text.strip()
    
    structured_match = re.search(r"SQL Query:\s*(SELECT .*?;)\s*Reasoning:\s*(.*)", cleaned_output, re.IGNORECASE | re.DOTALL)
    if structured_match:
        sql_query = structured_match.group(1).strip()
        reasoning = structured_match.group(2).strip()
    else:
        sql_only_match = re.search(r"(SELECT .*?;)", cleaned_output, re.IGNORECASE | re.DOTALL)
        if sql_only_match:
            sql_query = sql_only_match.group(1).strip()
            potential_reasoning = cleaned_output[sql_only_match.end():].strip()
            if potential_reasoning:
                reasoning = re.sub(r"^\s*Reasoning:\s*", "", potential_reasoning, flags=re.IGNORECASE).strip() or "A SQL query was found without reasoning text."
            else:
                reasoning = "A SQL query was found without reasoning text."
        else:
            reasoning = f"The model did not generate a valid SQL query. Output: {cleaned_output[:300]}..."
            if not cleaned_output:
                reasoning = "The model returned an empty output."

    reasoning = re.sub(r"<end_of_turn>.*", "", reasoning, flags=re.IGNORECASE | re.DOTALL).strip()
    return sql_query, reasoning

def _generate_sql_from_endpoint(prompt: str, endpoint_url: str, api_key: str, model_name: str, provider_name: str):
    # ... (Tidak ada perubahan di sini)
    if not endpoint_url:
        return "", f"The endpoint URL for provider '{provider_name}' is not configured."

    system_prompt = """You are an intelligent AI specialized in generating SQL queries from natural language.
You will be given a database table schema and a user question.
Your task is to generate a syntactically correct MySQL 8.0 query to answer the question and provide a brief reasoning.
Always write the reasoning in English, even when the user asks the question in another language.

The database contains the following tables:
1.  Table: `emotion_track`
    Columns: `id` (INT), `emotion` (VARCHAR(20)), `timestamp` (TIMESTAMP).
    Possible emotion values are: 'happy', 'sad', 'angry', 'fear', 'surprised'.
2.  Table: `clothing_track`
    Columns: `id` (INT), `label` (VARCHAR(50)), `confidence` (FLOAT), `timestamp` (TIMESTAMP).
    Possible clothing labels include: 'shorts', 'outer', 'skirt', 't-shirt', etc.
3.  Table: `head_track`
    Columns: `id` (INT), `label` (VARCHAR(50)), `confidence` (FLOAT), `timestamp` (TIMESTAMP).
    Possible headwear labels include: 'hijab', 'hat', etc.

You MUST select the correct table based on the user's query and make sure to change emotion or label to English and fit with the data. Use MySQL functions such as CURDATE(), YEARWEEK(), DATE_FORMAT(), HOUR(), and DATE(). Do not use PostgreSQL-specific syntax such as date_trunc, ILIKE, EXTRACT(... FROM ...), or timestamp::date.
Every query MUST contain a FROM clause and may only read the three tables listed above. Never generate SELECT COUNT(*) without FROM.
For a generic question about the number of data, detections, or visitors, use `emotion_track` as the canonical table. Do not add counts from all three tables because the same tracked event can be stored once in each table.
Example for "ada berapa data hari ini": SELECT COUNT(*) AS total_data FROM emotion_track WHERE DATE(timestamp) = CURDATE();
For every calculated or aggregate expression, always use a short, meaningful alias. Examples: COUNT(*) AS total, AVG(confidence) AS average_confidence, and DATE(timestamp) AS date. Never return raw expression names such as COUNT(*).

Structure your response EXACTLY as follows, with NO other text before or after 'SQL Query:':
SQL Query:
SELECT ...;
Reasoning:
Your reasoning here."""

    headers = { "Content-Type": "application/json" }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 400,
    }
    
    import json
    print("\n" + "="*50)
    print("DEBUGGING PAYLOAD YANG DIKIRIM KE GROQ")
    print(f"URL: {endpoint_url}")
    print("--- Headers ---")
    print(json.dumps(headers, indent=2))
    print("--- Payload ---")
    print(json.dumps(payload, indent=2))
    print("="*50 + "\n")

    try:
        print(f"NLP Service ({provider_name}): Mengirim request ke {endpoint_url}")
        response = requests.post(endpoint_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        api_response_data = response.json()

        content = api_response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not content:
            return "", f"The '{provider_name}' API response format is invalid or contains no content."

        print(f"\n=== RAW API OUTPUT ({provider_name}) ===\n{content}\n========================\n")
        return _parse_sql_and_reason(content)
    except requests.exceptions.RequestException as e:
        return "", f"Failed to connect to the '{provider_name}' API at {endpoint_url}. Error: {e}"
    except Exception as e:
        return "", f"Failed to process the '{provider_name}' API response: {e}"


def generate_sql_and_reason(prompt: str, config: Settings):
    """
    Fungsi utama yang menghasilkan SQL.
    Defaultnya Groq, dan akan memberikan error jika API key belum di-set.
    """
    print(f"NLP Service: Menghasilkan SQL dengan provider '{config.PROVIDER}'")

    known_query = _known_count_query(prompt)
    if known_query:
        return known_query
    
    if config.PROVIDER == 'groq':
        if not config.GROQ_API_KEY:
            error_msg = "The provider is set to 'groq', but the API key is not configured. Configure it in Chatbot Settings."
            return "", error_msg
            
        groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"
        return _generate_sql_from_endpoint(prompt, groq_endpoint, config.GROQ_API_KEY, config.GROQ_MODEL_NAME, "Groq")
    
    elif config.PROVIDER == 'local':
        if not config.LOCAL_ENDPOINT_URL:
            error_msg = "The provider is set to 'local', but the local endpoint URL is not configured."
            return "", error_msg
        return _generate_sql_from_endpoint(prompt, config.LOCAL_ENDPOINT_URL, "", "local-model", "Local")
    
    else:
        error_msg = f"Unsupported provider: '{config.PROVIDER}'. Select 'groq' or 'local'."
        return "", error_msg
