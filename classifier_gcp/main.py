from flask import Flask, request, jsonify
from transformers import BertTokenizer, BertConfig
from transformers.modeling_outputs import SequenceClassifierOutput
from transformers import BertPreTrainedModel, BertModel
import torch.nn as nn
import torch
import os

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
model = SmallerBERTClassifier.from_pretrained(MODEL_DIR, config=config)
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
        prediction = torch.argmax(probs).item()
        confidence = probs[prediction].item()

    return jsonify({
        "classification": "Misinformation" if prediction == 1 else "Not Misinformation",
        "confidence_score": round(confidence, 4)
    })

if __name__ == "__main__":
    app.run(debug=True)
