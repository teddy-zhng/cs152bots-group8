import torch
import torch.nn.functional as F
import pandas as pd
from pytorch_pretrained_bert import BertTokenizer, BertConfig
from model import BertForSequenceClassification
from tqdm import tqdm

# Load tokenizer and model config
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
config = BertConfig(vocab_size_or_config_json_file=32000, hidden_size=768,
                    num_hidden_layers=12, num_attention_heads=12, intermediate_size=3072)

# Load model and weights
model = BertForSequenceClassification(num_labels=2)
model.load_state_dict(torch.load("bert_model_finetuned.pth", map_location=torch.device('cpu')))
model.eval()

def preprocess(text, max_len):
    if not isinstance(text, str):
        text = "" if pd.isna(text) else str(text)
    tokens = tokenizer.tokenize(text if text else "None")
    tokens = tokens[:max_len]
    token_ids = tokenizer.convert_tokens_to_ids(tokens)
    padded = token_ids + [0] * (max_len - len(token_ids))
    return torch.tensor(padded).unsqueeze(0)  # shape: (1, max_len)

# Load dataset
df = pd.read_csv("../../LIAR-PLUS-master/dataset/tsv/train2.tsv", sep='\t')

df.columns = [f"col{i}" for i in range(len(df.columns))]
df = df.rename(columns={"col3": "statement", "col15": "justification"})
df = df.iloc[:1000].reset_index(drop=True)

predictions = []
confidences = []

for idx, row in tqdm(df.iterrows(), total=len(df)):
    if idx >= 1000:
        break
    statement = row.get("statement", "")
    # justification = row.get("justification", "")
    justification = ""
    metadata = ""
    credit = 0.5

    input_ids1 = preprocess(statement, max_len=64)
    input_ids2 = preprocess(justification, max_len=256)
    input_ids3 = preprocess(metadata, max_len=32)
    credit_tensor = torch.tensor([credit] * 2304).unsqueeze(0)  # shape (1, 2304)

    with torch.no_grad():
        logits = model(input_ids1, input_ids2, input_ids3, credit_tensor)
        probs = F.softmax(logits, dim=1)
        confidence = probs[0][1].item()
        prediction = "misinfo" if confidence > 0.5 else "not misinfo"

    predictions.append(prediction)
    confidences.append(round(confidence, 4))

df["prediction"] = predictions
df["confidence_score"] = confidences

df.to_csv("train2_preds_wout_justification.csv", index=False)