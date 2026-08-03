# backend/config.py
import json
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runtime_config.json')

class Settings:
    def __init__(self):
        # Setelan Database dari .env (tetap sama)
        self.DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
        self.DB_USER = os.getenv('DB_USER', 'trendbox-app')
        self.DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        self.DB_NAME = os.getenv('DB_NAME', os.getenv('DB_DATABASE', 'trendbox'))
        self.DB_PORT = int(os.getenv('DB_PORT', '3306'))
        self.INSTANCE_CONNECTION_NAME = os.getenv('INSTANCE_CONNECTION_NAME', '').strip()
        
        # Atribut ini akan diisi dari runtime_config.json
        # Defaultnya sekarang adalah 'groq'
        self.PROVIDER = 'groq'
        self.GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
        self.GROQ_MODEL_NAME = os.getenv('GROQ_MODEL_NAME', 'llama-3.1-8b-instant')
        
        # Opsi sekunder
        self.LOCAL_ENDPOINT_URL = '' 

    def load_config(self):
        """Membaca konfigurasi dari file JSON. Jika file tidak ada, akan dibuat dengan default Groq."""
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config_data = json.load(f)
                # Provider default adalah 'groq' jika tidak dispesifikasikan di file
                self.PROVIDER = config_data.get('provider', 'groq').lower()
                self.GROQ_API_KEY = os.getenv('GROQ_API_KEY', config_data.get('groq_api_key', ''))
                self.GROQ_MODEL_NAME = os.getenv('GROQ_MODEL_NAME', config_data.get('groq_model_name', 'llama-3.1-8b-instant'))
                self.LOCAL_ENDPOINT_URL = config_data.get('local_endpoint_url', '')
            print(f"Config: Berhasil memuat runtime_config.json. Provider aktif: '{self.PROVIDER}'")
        except FileNotFoundError:
            print(f"Config WARNING: File {CONFIG_FILE_PATH} tidak ditemukan. Membuat file dengan default Groq.")
            self.save_config() # Buat file dengan nilai default (Groq tanpa API key)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Config ERROR: Gagal membaca file JSON: {e}. Menggunakan nilai default.")

    def save_config(self):
        """Menyimpan konfigurasi saat ini ke file JSON."""
        config_data = {
            'provider': self.PROVIDER,
            'groq_api_key': self.GROQ_API_KEY,
            'groq_model_name': self.GROQ_MODEL_NAME,
            'local_endpoint_url': self.LOCAL_ENDPOINT_URL,
        }
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Config: Konfigurasi berhasil disimpan. Provider sekarang: '{self.PROVIDER}'")

# Instance tunggal untuk digunakan di seluruh aplikasi
settings = Settings()
# Langsung muat konfigurasi saat aplikasi dimulai
settings.load_config()
