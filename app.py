import logging
from transformers import logging as hf_logging

logging.getLogger("transformers").setLevel(logging.ERROR)
hf_logging.set_verbosity_error()
# app.py
import warnings
import os

# Suppress "Accessing __path__" and other library noise
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from groq import Groq

# -------------------------------
# Step 1: Load Dataset
# -------------------------------
csv_path = "D:/AI_SupplyChain_Project/Project1/orders.csv"
if not os.path.exists(csv_path):
    csv_path = "orders.csv"  # Fallback to current directory

try:
    orders = pd.read_csv(csv_path)
    print("\n✅ Dataset Loaded Successfully")
except Exception as e:
    print(f"❌ Error loading CSV: {e}")
    exit()

# -------------------------------
# Step 2: Transformation & Cleaning
# -------------------------------
orders.rename(columns={
    'SKU': 'ProductID',
    'Stock levels': 'StockLevel',
    'Location': 'WarehouseID'
}, inplace=True)

orders['Date'] = pd.to_datetime(pd.date_range(start='2026-01-01', periods=len(orders), freq='D'))
orders['Region'] = orders['WarehouseID']

# -------------------------------
# Step 3: Simulation & RAG Prep
# -------------------------------
np.random.seed(42)
deliveries = orders[['ProductID', 'WarehouseID', 'Date']].copy()
deliveries['DeliveryStatus'] = np.where(
    orders['Shipping times'] > orders['Shipping times'].mean(), 'Delayed', 'Delivered'
)
deliveries['DelayReason'] = deliveries['DeliveryStatus'].apply(
    lambda x: np.random.choice(['Traffic Issue', 'Supplier Delay', 'Low Stock']) if x == 'Delayed' else ''
)

historical_issues = deliveries.apply(
    lambda row: f"Product {row['ProductID']} in {row['WarehouseID']} was {row['DeliveryStatus']} due to {row['DelayReason']}",
    axis=1
).tolist()

# -------------------------------
# Step 4: Embeddings + FAISS
# -------------------------------
print("🤖 Initializing AI Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(historical_issues)
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(np.array(embeddings).astype('float32'))

# -------------------------------
# Step 5: Query & LLM
# -------------------------------
query = "Why are products getting delayed?"
query_embedding = model.encode([query]).astype('float32')
D, I = index.search(query_embedding, k=3)
context_text = "\n".join([historical_issues[i] for i in I[0]])

api_key = os.getenv("GROQ_API_KEY")
if api_key:
    client = Groq(api_key=api_key)
    prompt = f"Context:\n{context_text}\n\nQuestion: {query}\n\nGive: 1. Root cause 2. Recommendation"
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Supply chain expert"},
                      {"role": "user", "content": prompt}]
        )
        print("\n----- AI RESPONSE -----\n")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ Groq Error: {e}")
else:
    print("⚠️ API Key missing. Skipping LLM step.")
