import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from groq import Groq

# -------------------------------
# SETUP
# -------------------------------
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain AI", layout="wide")
st.title("🏛️ AI Supply Chain: Decision Intelligence System")

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
# LOAD DATA
# -------------------------------
df = pd.read_csv(CSV_FILE)

df.rename(columns={
    'SKU': 'ProductID',
    'Stock levels': 'StockLevel',
    'Location': 'WarehouseID'
}, inplace=True)

# Add missing columns safely
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
# METRICS
# -------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
col2.metric("Inventory Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
col3.metric("Transactions", len(st.session_state.history))

# -------------------------------
# ⭐ ENHANCEMENT 2: KPI CHARTS
# -------------------------------
st.write("## 📊 System Intelligence Dashboard")

c1, c2 = st.columns(2)

with c1:
    fig = px.pie(df, names='WarehouseID', title="Inventory Distribution by Warehouse")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    fig2 = px.bar(df.groupby("WarehouseID")["StockLevel"].mean().reset_index(),
                  x="WarehouseID", y="StockLevel",
                  title="Avg Stock Level by Warehouse")
    st.plotly_chart(fig2, use_container_width=True)

# -------------------------------
# QUERY SECTION
# -------------------------------
st.write("---")
st.subheader("🔍 Supply Chain Intelligence Query")

query = st.text_input("Search SKU (e.g., SKU1)").upper()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# -------------------------------
# MAIN LOGIC (YOUR SYSTEM + AI LAYER)
# -------------------------------
if query:

    match = df[df['ProductID'] == query]

    if not match.empty:
        row = match.iloc[0]

        st.info(f"""
        📦 Warehouse: {row['WarehouseID']}
        💰 Budget: ₹{row['Budget_INR']:,}
        📊 Stock: {row['StockLevel']}
        """)

        # find supplier candidates
        suppliers = df[df['WarehouseID'] != row['WarehouseID']].copy()
        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values("Distance").head(2)

        for i, s in suppliers.iterrows():

            st.markdown(f"### 🚚 Source: {s['WarehouseID']}")

            dist = s['Distance']
            unit_price = row['Unit_Price_INR']
            ship_cost = 0.75

            qty = st.number_input(
                f"Qty from {s['WarehouseID']}",
                min_value=0,
                max_value=int(s['StockLevel']),
                value=5,
                key=str(i)
            )

            product_cost = qty * unit_price
            freight = qty * dist * ship_cost
            total = product_cost + freight

            st.write(f"Product Cost: ₹{product_cost:,}")
            st.write(f"Freight Cost: ₹{freight:,}")
            st.write(f"Total Landed Cost: ₹{total:,}")

            if st.button(f"Confirm Transfer {i}"):

                if total <= row['Budget_INR']:

                    df.loc[row.name, 'StockLevel'] += qty
                    df.loc[row.name, 'Budget_INR'] -= total

                    df.loc[s.name, 'StockLevel'] -= qty
                    df.loc[s.name, 'Budget_INR'] += product_cost

                    st.success("Transaction Completed")
                    st.rerun()
                else:
                    st.error("Budget Exceeded")

        # -------------------------------
        # ⭐ ENHANCEMENT 1: AI PANEL
        # -------------------------------
        if client:

            prompt = f"""
You are a supply chain AI.

Data:
Warehouse: {row['WarehouseID']}
Stock: {row['StockLevel']}
Budget: {row['Budget_INR']}

Question: Why is this SKU inefficient?

Return in format:
1. Problem
2. Insight
3. Action Plan
"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            ai_output = response.choices[0].message.content

            st.subheader("🧠 AI Decision Report")
            st.write(ai_output)

            # -------------------------------
            # ⭐ ENHANCEMENT 3: EXPLAIN BUTTON
            # -------------------------------
            if st.button("🧾 Explain Simply"):
                explain = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{
                        "role": "user",
                        "content": f"Explain simply:\n{ai_output}"
                    }]
                )

                st.success("Simplified Explanation")
                st.write(explain.choices[0].message.content)

# -------------------------------
# TABLE VIEW
# -------------------------------
st.write("---")
st.subheader("📋 Full Inventory View")

st.dataframe(df, use_container_width=True)
