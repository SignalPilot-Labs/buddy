"""Solution for hf-model-inference challenge.
Downloads the model, creates Flask API, and starts it as a background service.
"""
import os
import sys

# Step 1: Download the model
print("Downloading model...")
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "/app/model_cache/sentiment_model"
os.makedirs(model_path, exist_ok=True)

model_name = "distilbert-base-uncased-finetuned-sst-2-english"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

tokenizer.save_pretrained(model_path)
model.save_pretrained(model_path)
print(f"Model saved to {model_path}")

# Step 2: Create the Flask app
flask_app_code = '''
from flask import Flask, request, jsonify
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

app = Flask(__name__)

model_path = "/app/model_cache/sentiment_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)
model.eval()

@app.route("/sentiment", methods=["POST"])
def sentiment():
    data = request.get_json(force=True)
    if "text" not in data:
        return jsonify({"error": "Missing 'text' field in request body"}), 400

    text = data["text"]
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)

    with torch.no_grad():
        outputs = model(**inputs)
        scores = torch.nn.functional.softmax(outputs.logits, dim=1)[0]

    negative_score = scores[0].item()
    positive_score = scores[1].item()

    sentiment_label = "positive" if positive_score > negative_score else "negative"

    return jsonify({
        "sentiment": sentiment_label,
        "confidence": {
            "positive": positive_score,
            "negative": negative_score
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
'''

with open("/app/sentiment_app.py", "w") as f:
    f.write(flask_app_code)

print("Flask app written to /app/sentiment_app.py")
print("Starting Flask app in background...")

# Step 3: Start the service
import subprocess
subprocess.Popen(
    [sys.executable, "/app/sentiment_app.py"],
    stdout=open("/tmp/flask.log", "w"),
    stderr=open("/tmp/flask.err", "w"),
)

# Wait for server to start
import time
import urllib.request

for i in range(30):
    time.sleep(1)
    try:
        urllib.request.urlopen("http://localhost:5000/sentiment",
                              data=b'{"text": "test"}')
        print("Flask app is running!")
        break
    except Exception:
        if i == 29:
            print("WARNING: Flask app may not have started")
        continue

print("Done!")
