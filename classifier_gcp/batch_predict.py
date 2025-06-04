import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from transformers import BertTokenizer, BertConfig
from transformers.modeling_outputs import SequenceClassifierOutput
from transformers import BertPreTrainedModel, BertModel
from tqdm import tqdm
import os
import safetensors.torch as st

# Model definition (copied from main.py)
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

# Paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_liar_bert_model")
WEIGHTS_PATH = os.path.join(MODEL_DIR, "model.safetensors")
TSV_PATH = "../../LIAR-PLUS-master/dataset/tsv/val2.tsv"
OUTPUT_CSV = "val2_preds.csv"

# Load tokenizer and model
tokenizer = BertTokenizer.from_pretrained(MODEL_DIR)
config = BertConfig.from_pretrained(MODEL_DIR)
model = SmallerBERTClassifier(config)

# Load weights from safetensors
state_dict = st.load_file(WEIGHTS_PATH)
model.load_state_dict(state_dict)
model.eval()

# Load dataset
df = pd.read_csv(TSV_PATH, sep='\t', header=None)
df.columns = [f"col{i}" for i in range(len(df.columns))]
# If justification is the last column, rename for clarity
df = df.rename(columns={"col3": "statement", "col15": "justification"})

predictions = []
confidences = []
misinfo_probs = []
not_misinfo_probs = []

for idx, row in tqdm(df.iterrows(), total=len(df)):
    if idx >= 1500:
        break
    statement = row.get("statement", "")
    justification = row.get("justification", "")

    # Ensure both are strings and handle NaN
    if not isinstance(statement, str):
        statement = "" if pd.isna(statement) else str(statement)
    if not isinstance(justification, str):
        justification = "" if pd.isna(justification) else str(justification)

    # Tokenize as in main.py
    inputs = tokenizer(
        statement,
        justification,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1).squeeze()
        # Lower the threshold for "misinfo" to prioritize recall
        threshold = 0.5  # adjust this value as needed
        if probs[1] >= threshold:
            prediction = 1
        else:
            prediction = 0
        confidence = probs[prediction].item()
        misinfo_prob = probs[1].item() # equals confidence if prediction == 1 otherwise equals 1 - confidence

    predictions.append("misinfo" if prediction == 1 else "not misinfo")
    confidences.append(round(confidence, 4))
    misinfo_probs.append(round(misinfo_prob, 4))

df = df.iloc[:1500].copy()

df["prediction"] = predictions
df["confidence_score"] = confidences
df["misinfo_prob"] = misinfo_probs

df.to_csv(OUTPUT_CSV, index=False)
print(f"Saved predictions to {OUTPUT_CSV}")