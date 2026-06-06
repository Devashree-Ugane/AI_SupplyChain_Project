import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# =========================
# 1. SETUP
# =========================
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")

st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

CSV_FILE = "orders.csv"

# =========================
# 2. DISTANCE MAP
# =========================
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

# =========================
# 3. DATA PROCESSING
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
# 4. LOAD STATE
# =========================
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("orders.csv not found")
        st.stop()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

df = st.session_state.df

# =========================
# 5. KPI SECTION (IMPROVED)
# =========================
st.subheader("📊 KPI Dashboard")

c1, c2, c3 = st.columns(3)

c1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
c2.metric("Inventory Value",
          f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}",
          delta="Live")

c3.metric("Transactions", len(st.session_state.transaction_history))

# =========================
# 6. SIMPLE CHARTS (LOW EFFORT HIGH IMPACT)
# =========================
st.subheader("📈 Operational Insights")

chart1 = df.groupby("WarehouseID")["StockLevel"].sum().reset_index()
fig1 = px.bar(chart1, x="WarehouseID", y="StockLevel", title="Stock by Warehouse")
st.plotly_chart(fig1, use_container_width=True)

chart2 = df.groupby("Category")["StockLevel"].sum().reset_index()
fig2 = px.pie(chart2, names="Category", values="StockLevel", title="Category Distribution")
st.plotly_chart(fig2, use_container_width=True)

# =========================
# 7. SEARCH ENGINE
# =========================
st.write("---")
st.subheader("🔍 Strategic Sourcing Engine")

target_sku = st.text_input("Search SKU").upper()

if target_sku:
    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:
        target_row = sku_rows.loc[sku_rows['StockLevel'].idxmin()]

        st.info(f"""
        Target: {target_row['WarehouseID']}
        Budget: ₹{target_row['Budget_INR']:,}
        Stock: {target_row['StockLevel']}
        """)

        suppliers = df[
            (df['WarehouseID'] != target_row['WarehouseID']) &
            (df['StockLevel'] > 0)
        ].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values(by='Distance').head(2)

        # =========================
        # FIXED LOOP (MAIN BUG FIX)
        # =========================
        for i, s in suppliers.iterrows():

            st.markdown("---")
            st.write(f"### Supplier: {s['WarehouseID']}")

            unit_price = target_row['Unit_Price_INR']
            dist = s['Distance']
            ship_rate = 0.75

            max_affordable = int(
                target_row['Budget_INR'] //
                max(1, (unit_price + dist * ship_rate))
            )

            # SAFE MAX VALUE
            safe_max = max(1, int(s['StockLevel']))

            move_qty = st.number_input(
                f"Qty from {s['WarehouseID']}",
                min_value=0,
                max_value=safe_max,
                value=min(5, safe_max),   # ✅ FIXED CRASH HERE
                key=f"qty_{i}"
            )

            prod_cost = move_qty * unit_price
            freight = int(move_qty * dist * ship_rate)
            total = prod_cost + freight

            st.write(f"Product: ₹{prod_cost:,}")
            st.write(f"Freight: ₹{freight:,}")
            st.write(f"Total: ₹{total:,}")

            if st.button(f"Execute {s['WarehouseID']}", key=f"btn_{i}"):

                if move_qty > 0 and total <= target_row['Budget_INR']:

                    st.session_state.df.loc[target_row.name, 'StockLevel'] += move_qty
                    st.session_state.df.loc[target_row.name, 'Budget_INR'] -= total

                    st.session_state.df.loc[s.name, 'StockLevel'] -= move_qty
                    st.session_state.df.loc[s.name, 'Budget_INR'] += prod_cost

                    st.session_state.transaction_history.append({
                        "sku": target_sku,
                        "from": s['WarehouseID'],
                        "to": target_row['WarehouseID'],
                        "qty": move_qty,
                        "val": total,
                        "dist": dist
                    })

                    save_data(st.session_state.df)
                    st.success("Transaction Completed")
                    st.rerun()

# =========================
# 8. CATEGORY LEDGER (RESTORED)
# =========================
st.write("---")
st.subheader("📋 Category Ledger")

for cat in df['Category'].unique():
    st.markdown(f"### {cat}")

    cat_df = df[df['Category'] == cat]

    risk = cat_df[cat_df['StockLevel'] < 10]

    if not risk.empty:
        st.warning(f"⚠ {len(risk)} low stock nodes")

    st.dataframe(cat_df, use_container_width=True)

# =========================
# 9. TRANSACTION HISTORY
# =========================
if st.session_state.transaction_history:
    st.write("---")
    st.subheader("📑 Transactions")

    for tx in reversed(st.session_state.transaction_history):
        st.write(tx)
