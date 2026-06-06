import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

warnings.filterwarnings("ignore")

# =========================
# APP CONFIG
# =========================
st.set_page_config(page_title="AI Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics + Risk + Intelligence Engine")

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
# DATA PROCESSING
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
# LOAD DATA
# =========================
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("orders.csv not found")
        st.stop()

if 'transactions' not in st.session_state:
    st.session_state.transactions = []

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

df = st.session_state.df

# =========================
# KPI DASHBOARD
# =========================
st.subheader("📊 KPI Dashboard")

c1, c2, c3 = st.columns(3)

c1.metric("Liquidity", f"₹{df['Budget_INR'].sum():,}")
c2.metric("Inventory Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
c3.metric("Transactions", len(st.session_state.transactions))

# =========================
# CHARTS
# =========================
st.subheader("📈 Analytics")

chart_df = df.groupby("WarehouseID")["StockLevel"].sum().reset_index()

fig = px.bar(chart_df, x="WarehouseID", y="StockLevel", title="Stock by Warehouse")
st.plotly_chart(fig, use_container_width=True)

# =========================
# AI CHAT PANEL (SAFE VERSION)
# =========================
st.subheader("🤖 AI Assistant")

query = st.text_input("Ask: Which nodes are at risk? / Optimize supply chain")

if query:
    risk_df = df[df['StockLevel'] < 10]

    if "risk" in query.lower():
        st.warning("🔴 Risk Analysis Engine")

        st.write(f"Total Risk Nodes: {len(risk_df)}")

        st.dataframe(risk_df[['WarehouseID', 'StockLevel', 'Category']])

    else:
        st.info("AI Response placeholder — connect Groq API here for full intelligence layer.")

# =========================
# SUPPLY CHAIN ENGINE
# =========================
st.write("---")
st.subheader("🔍 Supply Chain Optimization")

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

            safe_max = max(1, int(s['StockLevel']))

            qty = st.number_input(
                f"Qty from {s['WarehouseID']}",
                min_value=0,
                max_value=safe_max,
                value=min(3, safe_max),
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
                        "cost": total
                    })

                    save_data(st.session_state.df)
                    st.success("Transaction Completed")
                    st.rerun()

# =========================
# CATEGORY LEDGER (FIXED + SAFE RISK MARKING)
# =========================
st.write("---")
st.subheader("📋 Category Ledger")

for cat in df['Category'].unique():
    st.markdown(f"### 🏷️ {cat}")

    cat_df = df[df['Category'] == cat]

    risk = cat_df[cat_df['StockLevel'] < 10]

    if not risk.empty:
        st.error(f"🔴 {len(risk)} risk nodes detected")

    # SAFE DISPLAY (NO STYLER CRASH)
    display_df = cat_df.copy()
    display_df["Risk_Flag"] = display_df["StockLevel"].apply(
        lambda x: "🔴 LOW" if x < 10 else "🟢 OK"
    )

    st.dataframe(display_df, use_container_width=True)

# =========================
# TRANSACTION HISTORY
# =========================
st.write("---")
st.subheader("📑 Transaction History")

if st.session_state.transactions:
    st.dataframe(pd.DataFrame(st.session_state.transactions))
