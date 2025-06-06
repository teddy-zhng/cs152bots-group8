from flask import Flask, request, jsonify
from transformers import BertTokenizer, BertConfig
from transformers.modeling_outputs import SequenceClassifierOutput
from transformers import BertPreTrainedModel, BertModel
import torch.nn as nn
import torch
import os
from google.cloud import storage
import safetensors.torch as st
import io
import numpy as np


app = Flask(__name__)

# Define model architecture
class SmallerBERTClassifier(BertPreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(0.4)
        self.classifier = nn.Sequential(
            nn.Linear(config.hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, config.num_labels)
        )

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, labels=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids)
        pooled = self.dropout(outputs.pooler_output)
        logits = self.classifier(pooled)

        return SequenceClassifierOutput(
            loss=None,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions
        )

# ✅ Correct model directory name here
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_liar_bert_model")

# Load tokenizer and model from that directory
tokenizer = BertTokenizer.from_pretrained(MODEL_DIR)
config = BertConfig.from_pretrained(MODEL_DIR)
model = SmallerBERTClassifier(config)

# ✅ Load weights from Cloud Storage
def load_weights_from_gcs(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # 👇 Get raw bytes instead of using BytesIO
    weight_bytes = blob.download_as_bytes()

    # ✅ Load weights directly from bytes
    state_dict = st.load(weight_bytes)

    model.load_state_dict(state_dict)
    print("✅ Model weights loaded from GCS")

# 👇 Call this once, during init
load_weights_from_gcs("pol-disinfo-classifier", "model.safetensors")
model.eval()

@app.route("/classify", methods=["POST"])
def classify():
    data = request.json

    statement = data.get("message", "")
    justification = data.get("justification", "")  # optional

    if not statement.strip():
        return jsonify({"error": "The 'message' field (statement) is required."}), 400

    # Tokenize input
    inputs = tokenizer(statement, justification, return_tensors="pt", truncation=True, padding=True, max_length=256)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1).squeeze()
        # Lower the threshold for "misinfo" to prioritize recall
        threshold = 0.35  # adjust this value as needed
        if probs[1] >= threshold:
            prediction = 1
        else:
            prediction = 0
        confidence = probs[prediction].item()

    return jsonify({
        "classification": "Misinformation" if prediction == 1 else "Not Misinformation",
        "confidence_score": round(confidence, 4)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
