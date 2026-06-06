import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

CSV_FILE = "orders.csv"

# -------------------- DISTANCE MAP --------------------
DISTANCE_MAP = {
    'Mumbai': {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150, 'Chennai': 1300, 'Kolkata': 1900},
    'Delhi': {'Mumbai': 1400, 'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000, 'Delhi': 2100, 'Pune': 850, 'Chennai': 350, 'Kolkata': 1800},
    'Pune': {'Mumbai': 150, 'Delhi': 1450, 'Bangalore': 850, 'Chennai': 1200, 'Kolkata': 1850},
    'Chennai': {'Mumbai': 1300, 'Delhi': 2200, 'Bangalore': 350, 'Pune': 1200, 'Kolkata': 1600}
}

def get_distance(city1, city2):
    if city1 == city2:
        return 0
    return DISTANCE_MAP.get(city1, {}).get(city2, 800)

# -------------------- RISK ENGINE --------------------
def calculate_risk_score(stock, budget, distance_factor):
    stock_risk = max(0, 100 - stock * 5)
    budget_risk = max(0, 100 - budget / 3000)
    distance_risk = min(100, distance_factor / 20)

    score = (0.5 * stock_risk) + (0.3 * budget_risk) + (0.2 * distance_risk)
    return min(100, round(score))

# -------------------- AUTO REORDER ENGINE --------------------
def generate_reorder_suggestion(df, target_warehouse):
    target = df[df['WarehouseID'] == target_warehouse].iloc[0]

    suppliers = df[
        (df['WarehouseID'] != target_warehouse) &
        (df['StockLevel'] > 10)
    ].copy()

    if suppliers.empty:
        return None

    suppliers['Distance'] = suppliers['WarehouseID'].apply(
        lambda x: get_distance(target_warehouse, x)
    )

    suppliers['Score'] = suppliers.apply(
        lambda x: x['StockLevel'] / (1 + x['Distance']), axis=1
    )

    best = suppliers.sort_values(by='Score', ascending=False).iloc[0]

    qty = min(int(best['StockLevel'] * 0.2), 20)

    return {
        "from": best['WarehouseID'],
        "to": target_warehouse,
        "qty": max(1, qty),
        "distance": best['Distance']
    }

# -------------------- DATA PROCESSING --------------------
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

# -------------------- LOAD STATE --------------------
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("orders.csv not found.")
        st.stop()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

df = st.session_state.df

# -------------------- KPI METRICS --------------------
c1, c2, c3 = st.columns(3)

c1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
c2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
c3.metric("Transactions", len(st.session_state.transaction_history))

st.write("---")

# -------------------- SOURCING ENGINE --------------------
st.subheader("🔍 Strategic Sourcing Engine")

target_sku = st.text_input("Enter SKU").upper()

if target_sku:
    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:
        target_row = sku_rows.loc[sku_rows['StockLevel'].idxmin()]

        st.info(
            f"Target: {target_row['WarehouseID']} | "
            f"Budget: ₹{target_row['Budget_INR']:,} | "
            f"Stock: {target_row['StockLevel']}"
        )

        suppliers = df[
            (df['WarehouseID'] != target_row['WarehouseID']) &
            (df['StockLevel'] > 5)
        ].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values(by='Distance').head(2)

        for idx, supplier in suppliers.iterrows():

            col1, col2, col3 = st.columns([2, 1, 1])

            unit_price = target_row['Unit_Price_INR']
            dist = supplier['Distance']
            ship_rate = 0.75

            safe_max = max(0, int(supplier['StockLevel']))
            qty = st.number_input(
                f"Qty from {supplier['WarehouseID']}",
                min_value=0,
                max_value=safe_max,
                value=min(5, safe_max),
                key=f"qty_{idx}"
            )

            prod_cost = qty * unit_price
            freight = int(qty * dist * ship_rate)
            total = prod_cost + freight

            with col1:
                st.write(f"Supplier: {supplier['WarehouseID']}")
                st.write(f"Distance: {dist} km")

            with col2:
                st.write(f"Product: ₹{prod_cost}")
                st.write(f"Freight: ₹{freight}")
                st.write(f"Total: ₹{total}")

            with col3:
                if total > target_row['Budget_INR']:
                    st.error("Insolvent")
                elif st.button(f"Confirm {idx}", key=f"btn_{idx}"):
                    st.session_state.df.loc[target_row.name, 'StockLevel'] += qty
                    st.session_state.df.loc[target_row.name, 'Budget_INR'] -= total

                    st.session_state.df.loc[supplier.name, 'StockLevel'] -= qty
                    st.session_state.df.loc[supplier.name, 'Budget_INR'] += prod_cost

                    st.session_state.transaction_history.append({
                        "sku": target_sku,
                        "from": supplier['WarehouseID'],
                        "to": target_row['WarehouseID'],
                        "qty": qty,
                        "value": total
                    })

                    save_data(st.session_state.df)
                    st.success("Transaction Complete")
                    st.rerun()

# -------------------- AUTO REORDER ENGINE UI --------------------
st.write("---")
st.subheader("🔁 Auto Reorder Intelligence")

low_nodes = df[df['StockLevel'] < 10]['WarehouseID'].unique()

if len(low_nodes) > 0:
    for node in low_nodes:
        sug = generate_reorder_suggestion(df, node)

        if sug:
            st.info(
                f"""
                From: {sug['from']}
                To: {sug['to']}
                Qty: {sug['qty']}
                Distance: {sug['distance']} km
                """
            )
else:
    st.success("All systems stable")

# -------------------- CATEGORY LEDGER --------------------
st.write("---")
st.subheader("📋 Category Ledger")

for cat in sorted(df['Category'].unique()):
    st.markdown(f"### {cat}")

    cat_df = df[df['Category'] == cat].copy()

    # Risk Score
    cat_df["RiskScore"] = cat_df.apply(
        lambda r: calculate_risk_score(
            r["StockLevel"],
            r["Budget_INR"],
            get_distance(r["WarehouseID"], "Mumbai")
        ),
        axis=1
    )

    def style(row):
        if row['StockLevel'] < 10 and row['Budget_INR'] < 40000:
            return ['background-color:#ffdddd; color:black'] * len(row)
        elif row['StockLevel'] < 10:
            return ['background-color:#fff4cc; color:black'] * len(row)
        return [''] * len(row)

    st.dataframe(cat_df.style.apply(style, axis=1), width='stretch')

# -------------------- TRANSACTIONS --------------------
if st.session_state.transaction_history:
    st.write("---")
    st.subheader("📑 Transaction Log")

    for tx in reversed(st.session_state.transaction_history):
        st.json(tx)
