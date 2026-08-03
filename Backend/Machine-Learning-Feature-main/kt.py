import os

print("Mencari file dengan encoding non-UTF-8...")

# Ganti '.' dengan path lain jika perlu
project_path = '.' 

for root, _, files in os.walk(project_path):
    # Abaikan folder virtual environment
    if '.venv' in root or '__pycache__' in root:
        continue

    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    f.read()
            except UnicodeDecodeError:
                print(f">>> File bermasalah ditemukan: {filepath}")

print("Pencarian selesai.")