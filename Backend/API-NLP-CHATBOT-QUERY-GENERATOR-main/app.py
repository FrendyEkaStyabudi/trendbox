import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from systemservice.nlp_service import generate_sql_and_reason
from systemservice.db_service import execute_sql_query
# HANYA IMPORT 'settings' global, bukan kelas 'Settings'
from config import settings

app = Flask(__name__)

origins_env = os.getenv("FRONTEND_ORIGINS", "*")
origins = "*" if origins_env.strip() == "*" else [origin.strip() for origin in origins_env.split(",") if origin.strip()]
CORS(app, resources={r"/api/*": {"origins": origins}})

@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'nlp-api'})

# === ENDPOINT UNTUK PENGATURAN ===

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Mengembalikan konfigurasi saat ini dari objek global."""
    # TIDAK PERLU membuat objek baru, langsung gunakan 'settings' yang sudah diimpor
    return jsonify({
        'provider': settings.PROVIDER,
        'local_endpoint_url': settings.LOCAL_ENDPOINT_URL,
        'groq_api_key': '',
        'groq_api_key_configured': bool(settings.GROQ_API_KEY),
        'groq_model_name': settings.GROQ_MODEL_NAME
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Menerima dan menyimpan konfigurasi baru, lalu memuat ulang ke objek global."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "The JSON request body is missing."}), 400

    # Update atribut di objek 'settings' global
    settings.PROVIDER = data.get('provider', settings.PROVIDER).lower()
    settings.LOCAL_ENDPOINT_URL = data.get('local_endpoint_url', settings.LOCAL_ENDPOINT_URL)
    settings.GROQ_API_KEY = data.get('groq_api_key', settings.GROQ_API_KEY)
    settings.GROQ_MODEL_NAME = data.get('groq_model_name', settings.GROQ_MODEL_NAME)
    
    try:
        # Simpan perubahan ke file
        settings.save_config()
        # Muat ulang konfigurasi ke objek global untuk memastikan konsistensi
        settings.load_config() 
        return jsonify({"message": "Settings saved successfully."}), 200
    except Exception as e:
        print(f"App Error: Gagal menyimpan konfigurasi: {e}")
        return jsonify({"error": f"Failed to save the configuration: {e}"}), 500

# === ENDPOINT CHAT ===

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def handle_chat():
    if request.method == 'OPTIONS':
        return jsonify(success=True), 200

    # TIDAK PERLU membuat objek baru. Langsung gunakan 'settings' global.
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error_message": "The request body must be JSON with a 'query' field."}), 400

    user_prompt = data['query']
    print(f"App.py: Menerima prompt '{user_prompt}' dengan provider '{settings.PROVIDER}'")

    response_data = {
        "original_prompt": user_prompt, "generated_sql": None, "reasoning": None,
        "query_result": None, "error_message": None, "info_message": None, "has_chart_data": False
    }

    # Gunakan 'settings' global saat memanggil service
    sql_query, reason = generate_sql_and_reason(user_prompt, settings)
    
    # ... sisa logika fungsi handle_chat Anda (tidak perlu diubah) ...
    response_data["generated_sql"] = sql_query
    response_data["reasoning"] = reason

    if sql_query:
        db_result = execute_sql_query(sql_query)
        if db_result.get("error"):
            response_data["error_message"] = f"SQL execution error: {db_result['error']}"
        else:
            response_data["query_result"] = db_result.get("data")
            response_data["info_message"] = db_result.get("info")
    elif reason:
        if any(term in reason.lower() for term in ("failed", "error", "invalid", "not configured", "unsupported")):
            response_data["error_message"] = reason
        else:
            response_data["info_message"] = reason
    else:
        response_data["error_message"] = "The NLP service did not return SQL or reasoning."

    query_res = response_data.get("query_result")
    if query_res and isinstance(query_res, list) and len(query_res) > 0:
        first_row = query_res[0]
        if isinstance(first_row, dict) and not (("Info" in first_row) or ("Error" in first_row) or ("affected_rows" in first_row)):
            response_data["has_chart_data"] = True
    
    print(f"App.py: Mengirim respons (pratinjau): {str(response_data)[:400]}...")
    return jsonify(response_data)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    print(f"Memulai server Flask secara lokal di port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)

