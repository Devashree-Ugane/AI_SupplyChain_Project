import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")

st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

CSV_FILE = "orders.csv"

# -----------------------------
# DISTANCE MAP
# -----------------------------
DISTANCE_MAP = {
    'Mumbai': {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150, 'Chennai': 1300, 'Kolkata': 1900},
    'Delhi': {'Mumbai': 1400, 'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000, 'Delhi': 2100, 'Pune': 850, 'Chennai': 350, 'Kolkata': 1800},
    'Pune': {'Mumbai': 150, 'Delhi': 1450, 'Bangalore': 850, 'Chennai': 1200, 'Kolkata': 1850},
    'Chennai': {'Mumbai': 1300, 'Delhi': 2200, 'Bangalore': 350, 'Pune': 1200, 'Kolkata': 1600}
}

def get_distance(c1, c2):
    if c1 == c2:
        return 0
    return DISTANCE_MAP.get(c1, {}).get(c2, 800)

def process_dataframe(df):
    df.rename(columns={
        'SKU': 'ProductID',
        'Stock levels': 'StockLevel',
        'Location': 'WarehouseID'
    }, inplace=True)

    if 'Category' not in df.columns:
        df['Category'] = np.random.choice(
            ['Haircare', 'Skincare', 'Wellness', 'Cosmetics'],
            size=len(df)
        )

    if 'Budget_INR' not in df.columns:
        df['Budget_INR'] = np.random.randint(80000, 300000, len(df))

    if 'Unit_Price_INR' not in df.columns:
        df['Unit_Price_INR'] = np.random.randint(2000, 8000, len(df))

    return df

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# -----------------------------
# LOAD DATA
# -----------------------------
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("orders.csv not found")
        st.stop()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

df = st.session_state.df

# -----------------------------
# KPI DELTA (NEW)
# -----------------------------
st.subheader("📊 Live KPI Dashboard")

total_budget = df['Budget_INR'].sum()
total_stock_value = (df['StockLevel'] * df['Unit_Price_INR']).sum()
transactions = len(st.session_state.transaction_history)

st.metric("Network Liquidity", f"₹{total_budget:,}", delta="+2.3% simulated")
st.metric("Inventory Asset Value", f"₹{total_stock_value:,}", delta="+1.1% simulated")
st.metric("Settled Transactions", transactions, delta=1 if transactions > 0 else 0)

st.write("---")

# -----------------------------
# CHATBOT PANEL (NEW)
# -----------------------------
st.subheader("🤖 AI Supply Chain Assistant")

query = st.text_input("Ask anything (e.g. Which warehouse is at risk?)")

if query:
    # placeholder logic (replace with Groq API later)
    if "risk" in query.lower():
        answer = "High risk detected in low-stock + low-budget nodes across Tier-2 warehouses."
    elif "warehouse" in query.lower():
        answer = "Mumbai and Pune hubs show optimal balance between stock and liquidity."
    else:
        answer = "System is analyzing supply chain patterns..."

    st.info(answer)

st.write("---")

# -----------------------------
# CHARTS (NEW)
# -----------------------------

col1, col2, col3 = st.columns(3)

with col1:
    fig = px.bar(df, x="WarehouseID", y="StockLevel", title="Stock by Warehouse")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    risky = df[df['StockLevel'] < 10].shape[0]
    safe = df.shape[0] - risky
    fig = px.pie(values=[risky, safe], names=["Risk", "Safe"], title="Risk Distribution")
    st.plotly_chart(fig, use_container_width=True)

with col3:
    df_sorted = df.sort_values("Budget_INR")
    fig = px.line(df_sorted, x="WarehouseID", y="Budget_INR", title="Budget Trend")
    st.plotly_chart(fig, use_container_width=True)

st.write("---")

# -----------------------------
# SEARCH & TRANSACTION ENGINE (UNCHANGED CORE)
# -----------------------------
st.subheader("🔍 Strategic Sourcing Engine")

target_sku = st.text_input("Search SKU").upper()

if target_sku:
    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:
        target_row = sku_rows.loc[sku_rows['StockLevel'].idxmin()]

        st.info(f"Target: {target_row['WarehouseID']} | Budget: ₹{target_row['Budget_INR']:,}")

        suppliers = df[(df['WarehouseID'] != target_row['WarehouseID']) &
                       (df['StockLevel'] > 5)].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values("Distance").head(2)

        for idx, s in suppliers.iterrows():

            unit_price = target_row['Unit_Price_INR']
            dist = s['Distance']
            ship_rate = 0.75

            max_affordable = int(target_row['Budget_INR'] //
                                 (unit_price + dist * ship_rate))

            max_val = int(s['StockLevel'])

            # FIXED SAFE VALUE
            default_qty = min(max_affordable, max_val, 5)
            if default_qty < 0:
                default_qty = 0

            with st.container():
                colA, colB, colC = st.columns(3)

                with colA:
                    st.write(f"### {s['WarehouseID']}")
                    st.write(f"Stock: {s['StockLevel']}")
                    st.write(f"Distance: {dist} km")

                with colB:
                    qty = st.number_input(
                        f"Qty from {s['WarehouseID']}",
                        min_value=0,
                        max_value=max_val,
                        value=default_qty,
                        key=str(idx)
                    )

                    prod_cost = qty * unit_price
                    ship_cost = qty * dist * ship_rate
                    total = prod_cost + ship_cost

                    st.write(f"Product: ₹{prod_cost:,}")
                    st.write(f"Freight: ₹{ship_cost:,}")
                    st.write(f"Total: ₹{total:,}")

                with colC:
                    if qty == 0:
                        st.warning("Select quantity")
                    elif total > target_row['Budget_INR']:
                        st.error("Budget exceeded")
                    else:
                        if st.button("Confirm", key=f"btn_{idx}"):

                            st.session_state.df.loc[target_row.name, 'StockLevel'] += qty
                            st.session_state.df.loc[target_row.name, 'Budget_INR'] -= total

                            st.session_state.df.loc[s.name, 'StockLevel'] -= qty
                            st.session_state.df.loc[s.name, 'Budget_INR'] += prod_cost

                            st.session_state.transaction_history.append({
                                "sku": target_sku,
                                "from": s['WarehouseID'],
                                "to": target_row['WarehouseID'],
                                "qty": qty,
                                "cost": total,
                                "distance": dist
                            })

                            save_data(st.session_state.df)
                            st.rerun()

st.write("---")

# -----------------------------
# CATEGORY LEDGER (RESTORED FIX)
# -----------------------------
st.subheader("📋 Category Ledger")

for cat in df['Category'].unique():
    st.markdown(f"### {cat}")
    cat_df = df[df['Category'] == cat]

    st.dataframe(cat_df, use_container_width=True)

st.write("---")

# -----------------------------
# EXPORT BUTTON (NEW)
# -----------------------------
st.download_button(
    "⬇ Export Data as CSV",
    df.to_csv(index=False),
    file_name="supply_chain_export.csv",
    mime="text/csv"
)

# -----------------------------
# TRANSACTION HISTORY
# -----------------------------
if st.session_state.transaction_history:
    st.subheader("📜 Transaction Log")

    for tx in reversed(st.session_state.transaction_history):
        st.write(tx)
