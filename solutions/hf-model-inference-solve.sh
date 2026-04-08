#!/bin/bash
set -e

pip install flask transformers torch

cat > /app/download_model.py << 'PYEOF'
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import os

model_path = "/app/model_cache/sentiment_model"
os.makedirs(model_path, exist_ok=True)

model_name = "distilbert-base-uncased-finetuned-sst-2-english"
model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

model.save_pretrained(model_path)
tokenizer.save_pretrained(model_path)
print("Model saved!")
PYEOF

python3 /app/download_model.py

cat > /app/server.py << 'PYEOF'
from flask import Flask, request, jsonify
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

app = Flask(__name__)

model_path = "/app/model_cache/sentiment_model"
model = AutoModelForSequenceClassification.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)
model.eval()

@app.route("/sentiment", methods=["POST"])
def sentiment():
    data = request.get_json(force=True, silent=True) or {}
    if "text" not in data or not data["text"]:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"]
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

    neg_score = float(probs[0])
    pos_score = float(probs[1])

    sentiment_label = "positive" if pos_score >= neg_score else "negative"

    return jsonify({
        "sentiment": sentiment_label,
        "confidence": {
            "positive": pos_score,
            "negative": neg_score,
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
PYEOF

nohup python3 /app/server.py > /tmp/flask.log 2>&1 &
sleep 5

# Test
curl -s -X POST http://localhost:5000/sentiment -H "Content-Type: application/json" -d '{"text": "This is great!"}'
echo ""
echo "Server started!"
