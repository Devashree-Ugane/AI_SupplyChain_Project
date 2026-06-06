import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

warnings.filterwarnings("ignore")

st.set_page_config(page_title="AI Supply Chain", layout="wide")

st.title("🏛️ AI Supply Chain: Intelligent Logistics & Risk Engine")

CSV_FILE = "orders.csv"

# =========================
# DISTANCE MAP
# =========================
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

# =========================
# DATA PREP
# =========================
def process_dataframe(df):
    df.rename(columns={
        'SKU': 'ProductID',
        'Stock levels': 'StockLevel',
        'Location': 'WarehouseID'
    }, inplace=True)

    if 'Category' not in df.columns:
        df['Category'] = np.random.choice(
            ['Haircare', 'Skincare', 'Wellness', 'Cosmetics'],
            len(df)
        )

    if 'Budget_INR' not in df.columns:
        df['Budget_INR'] = np.random.randint(80000, 300000, len(df))

    if 'Unit_Price_INR' not in df.columns:
        df['Unit_Price_INR'] = np.random.randint(2000, 8000, len(df))

    return df

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# =========================
# LOAD STATE
# =========================
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("orders.csv missing")
        st.stop()

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'transactions' not in st.session_state:
    st.session_state.transactions = []

df = st.session_state.df

# =========================
# KPI SECTION
# =========================
st.subheader("📊 KPI Dashboard")

c1, c2, c3 = st.columns(3)

c1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
c2.metric("Inventory Value",
          f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
c3.metric("Transactions", len(st.session_state.transactions))

# =========================
# CHARTS
# =========================
st.subheader("📈 Analytics Dashboard")

fig1 = px.bar(df.groupby("WarehouseID")["StockLevel"].sum().reset_index(),
              x="WarehouseID", y="StockLevel",
              title="Stock Distribution")

st.plotly_chart(fig1, use_container_width=True)

# =========================
# AI CHATBOT PANEL (NEW)
# =========================
st.subheader("🤖 AI Supply Chain Assistant")

user_query = st.text_input("Ask something like: Which nodes are at risk?")

if user_query:
    # lightweight rule-based + placeholder for Groq integration
    risk_nodes = df[df['StockLevel'] < 10]

    if "risk" in user_query.lower():
        st.success("AI Insight Generated:")

        st.write("### 🔴 Risk Analysis")
        st.write(f"{len(risk_nodes)} nodes are at risk due to low stock.")

        st.write("### 📍 Affected Warehouses")
        st.write(risk_nodes[['WarehouseID', 'StockLevel']])

    else:
        st.info("AI Response (simulated): Connect Groq API here for full LLM responses.")

# =========================
# SUPPLY CHAIN ENGINE
# =========================
st.write("---")
st.subheader("🔍 Supply Chain Optimization Engine")

sku = st.text_input("Enter SKU").upper()

if sku:
    sku_rows = df[df['ProductID'] == sku]

    if not sku_rows.empty:
        target = sku_rows.loc[sku_rows['StockLevel'].idxmin()]

        st.info(f"""
        Target Warehouse: {target['WarehouseID']}
        Budget: ₹{target['Budget_INR']:,}
        Stock: {target['StockLevel']}
        """)

        suppliers = df[(df['WarehouseID'] != target['WarehouseID']) &
                        (df['StockLevel'] > 0)].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values("Distance").head(2)

        for i, s in suppliers.iterrows():

            st.markdown("---")

            unit_price = target['Unit_Price_INR']
            dist = s['Distance']
            ship_rate = 0.75

            max_affordable = int(target['Budget_INR'] // max(1, unit_price + dist * ship_rate))

            safe_max = max(1, int(s['StockLevel']))

            qty = st.number_input(
                f"Qty from {s['WarehouseID']}",
                min_value=0,
                max_value=safe_max,
                value=min(5, safe_max),
                key=f"qty_{i}"
            )

            total = qty * unit_price + qty * dist * ship_rate

            st.write(f"Total Cost: ₹{total:,.0f}")

            if st.button(f"Execute {s['WarehouseID']}", key=f"btn_{i}"):

                if qty > 0 and total <= target['Budget_INR']:

                    st.session_state.df.loc[target.name, 'StockLevel'] += qty
                    st.session_state.df.loc[target.name, 'Budget_INR'] -= total

                    st.session_state.df.loc[s.name, 'StockLevel'] -= qty
                    st.session_state.df.loc[s.name, 'Budget_INR'] += qty * unit_price

                    st.session_state.transactions.append({
                        "from": s['WarehouseID'],
                        "to": target['WarehouseID'],
                        "qty": qty,
                        "value": total
                    })

                    save_data(st.session_state.df)
                    st.success("Transaction Complete")
                    st.rerun()

# =========================
# CATEGORY LEDGER (RESTORED + RISK HIGHLIGHT)
# =========================
st.write("---")
st.subheader("📋 Category-wise Ledger")

for cat in df['Category'].unique():
    st.markdown(f"### 🏷️ {cat}")

    cat_df = df[df['Category'] == cat]

    risk = cat_df[cat_df['StockLevel'] < 10]

    if not risk.empty:
        st.error(f"🔴 {len(risk)} RISK nodes in {cat}")

    styled = cat_df.style.apply(
        lambda x: ['background-color: #ffcccc' if v < 10 else '' for v in x['StockLevel']],
        axis=1
    )

    st.dataframe(styled, use_container_width=True)

# =========================
# TRANSACTION LOG
# =========================
st.write("---")
st.subheader("📑 Transaction History")

for t in reversed(st.session_state.transactions):
    st.write(t)
