import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from groq import Groq

# -------------------------------
# BASE SETUP (UNCHANGED STYLE)
# -------------------------------
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

CSV_FILE = "orders.csv"

# -------------------------------
# DISTANCE MAP (UNCHANGED)
# -------------------------------
DISTANCE_MAP = {
    'Mumbai': {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150, 'Chennai': 1300, 'Kolkata': 1900},
    'Delhi': {'Mumbai': 1400, 'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000, 'Delhi': 2100, 'Pune': 850, 'Chennai': 350, 'Kolkata': 1800},
    'Pune': {'Mumbai': 150, 'Delhi': 1450, 'Bangalore': 850, 'Chennai': 1200, 'Kolkata': 1850},
    'Chennai': {'Mumbai': 1300, 'Delhi': 2200, 'Bangalore': 350, 'Pune': 1200, 'Kolkata': 1600}
}

def get_distance(a, b):
    if a == b:
        return 0
    return DISTANCE_MAP.get(a, {}).get(b, 800)

# -------------------------------
# LOAD DATA (UNCHANGED LOGIC)
# -------------------------------
df = pd.read_csv(CSV_FILE)

df.rename(columns={
    'SKU': 'ProductID',
    'Stock levels': 'StockLevel',
    'Location': 'WarehouseID'
}, inplace=True)

if 'Category' not in df.columns:
    df['Category'] = np.random.choice(['Haircare', 'Skincare', 'Wellness', 'Cosmetics'], len(df))

if 'Budget_INR' not in df.columns:
    df['Budget_INR'] = np.random.randint(80000, 300000, len(df))

if 'Unit_Price_INR' not in df.columns:
    df['Unit_Price_INR'] = np.random.randint(2000, 8000, len(df))

# -------------------------------
# SESSION STATE
# -------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

# -------------------------------
# KPI SECTION (ENHANCED WITH DELTA)
# -------------------------------
st.subheader("📊 KPI Dashboard")

total_stock = df['StockLevel'].sum()
total_budget = df['Budget_INR'].sum()

col1, col2, col3 = st.columns(3)

col1.metric("Total Stock", total_stock, delta=np.random.randint(-5, 15))
col2.metric("Total Budget", f"₹{total_budget:,}", delta=np.random.randint(-20000, 30000))
col3.metric("Transactions", len(st.session_state.history), delta=np.random.randint(0, 5))

# -------------------------------
# ⭐ PLOTLY CHARTS (NEW)
# -------------------------------
st.write("## 📈 Operational Intelligence")

c1, c2, c3 = st.columns(3)

with c1:
    fig = px.bar(df.groupby("WarehouseID")["StockLevel"].sum().reset_index(),
                 x="WarehouseID", y="StockLevel",
                 title="Stock Level by Warehouse")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    fig2 = px.pie(df, names="Category", title="Category Distribution")
    st.plotly_chart(fig2, use_container_width=True)

with c3:
    fig3 = px.line(df.groupby("WarehouseID")["Budget_INR"].mean().reset_index(),
                   x="WarehouseID", y="Budget_INR",
                   title="Budget Utilization Trend")
    st.plotly_chart(fig3, use_container_width=True)

# -------------------------------
# DATA AUDIT TABLE
# -------------------------------
st.write("---")
st.subheader("📋 Inventory Ledger")

st.dataframe(df, use_container_width=True)

# -------------------------------
# ⭐ EXPORT BUTTON (NEW)
# -------------------------------
csv_data = df.to_csv(index=False).encode('utf-8')

st.download_button(
    label="📥 Download Inventory CSV",
    data=csv_data,
    file_name="inventory_audit.csv",
    mime="text/csv"
)

# -------------------------------
# MAIN TRANSACTION SYSTEM (UNCHANGED IDEA)
# -------------------------------
st.write("---")
st.subheader("🔍 Strategic Sourcing Engine")

target = st.text_input("Enter SKU (e.g., SKU1)").upper()

if target:

    row_match = df[df['ProductID'] == target]

    if not row_match.empty:

        target_row = row_match.iloc[0]

        st.info(f"""
        📍 Warehouse: {target_row['WarehouseID']}
        💰 Budget: ₹{target_row['Budget_INR']:,}
        📦 Stock: {target_row['StockLevel']}
        """)

        suppliers = df[df['WarehouseID'] != target_row['WarehouseID']].copy()
        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values("Distance").head(2)

        for i, s in suppliers.iterrows():

            st.markdown(f"### 🚚 Supplier: {s['WarehouseID']}")

            qty = st.number_input(f"Qty from {s['WarehouseID']}",
                                   min_value=0,
                                   max_value=int(s['StockLevel']),
                                   value=5,
                                   key=str(i))

            cost = qty * target_row['Unit_Price_INR']
            freight = qty * s['Distance'] * 0.75
            total = cost + freight

            st.write(f"Cost: ₹{cost:,}")
            st.write(f"Freight: ₹{freight:,}")
            st.write(f"Total: ₹{total:,}")

            if st.button(f"Execute Transfer {i}"):

                if total <= target_row['Budget_INR']:

                    df.loc[target_row.name, 'StockLevel'] += qty
                    df.loc[target_row.name, 'Budget_INR'] -= total

                    df.loc[s.name, 'StockLevel'] -= qty
                    df.loc[s.name, 'Budget_INR'] += cost

                    st.success("Transaction Successful")
                    st.rerun()

                else:
                    st.error("Budget Exceeded")

        # -------------------------------
        # ⭐ 1. AI CHATBOT PANEL (NEW BIG FEATURE)
        # -------------------------------
        st.write("---")
        st.subheader("🤖 AI Supply Chain Chatbot")

        api_key = os.getenv("GROQ_API_KEY")
        client = Groq(api_key=api_key) if api_key else None

        chat_query = st.text_input("Ask anything (e.g. Which warehouse is at risk?)")

        if chat_query and client:

            context = df.sample(10).to_string()

            prompt = f"""
You are a supply chain AI assistant.

Context:
{context}

User Question:
{chat_query}

Give precise and actionable answer.
"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            answer = response.choices[0].message.content

            st.subheader("🧠 AI Response")
            st.write(answer)

# -------------------------------
# TRANSACTION HISTORY
# -------------------------------
if st.session_state.history:
    st.write("---")
    st.subheader("📑 Transaction History")

    for h in st.session_state.history:
        st.write(h)
