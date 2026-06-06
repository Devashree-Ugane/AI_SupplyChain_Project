import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3

# =========================
# 1. SETUP
# =========================
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

DB_FILE = "supplychain.db"
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

def get_distance(city1, city2):
    if city1 == city2:
        return 0
    return DISTANCE_MAP.get(city1, {}).get(city2, 800)

# =========================
# 3. SQLITE FUNCTIONS
# =========================
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def create_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS warehouse_data (
            ProductID TEXT,
            StockLevel INTEGER,
            WarehouseID TEXT,
            Category TEXT,
            Budget_INR INTEGER,
            Unit_Price_INR INTEGER
        )
    """)
    conn.commit()
    conn.close()

def load_csv_to_db():
    if not os.path.exists(CSV_FILE):
        return

    df = pd.read_csv(CSV_FILE)

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

    conn = get_conn()
    df.to_sql("warehouse_data", conn, if_exists="replace", index=False)
    conn.close()

def load_data():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM warehouse_data", conn)
    conn.close()
    return df

def save_data(df):
    conn = get_conn()
    df.to_sql("warehouse_data", conn, if_exists="replace", index=False)
    conn.close()

# =========================
# 4. INIT DB + LOAD DATA
# =========================
create_table()

if not os.path.exists(DB_FILE):
    load_csv_to_db()

if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

df = st.session_state.df

# =========================
# 5. TOP METRICS
# =========================
m1, m2, m3 = st.columns(3)

m1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
m3.metric("Settled Transactions", len(st.session_state.transaction_history))

# =========================
# 6. SEARCH ENGINE
# =========================
st.write("---")
st.subheader("🔍 Strategic Sourcing & Landed Cost Optimization")

target_sku = st.text_input("Search SKU (e.g., SKU1):").upper()

if target_sku:

    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:

        target_row = sku_rows.iloc[0]

        st.info(
            f"**Target Node:** {target_row['WarehouseID']} | "
            f"Budget: ₹{target_row['Budget_INR']:,} | "
            f"Stock: {target_row['StockLevel']}"
        )

        suppliers = df[
            (df['WarehouseID'] != target_row['WarehouseID']) &
            (df['StockLevel'] > 0)
        ].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values(by='Distance').head(2)

        for idx, supplier in suppliers.iterrows():

            with st.container(border=True):

                c1, c2, c3 = st.columns([2, 1, 1])

                unit_price = target_row['Unit_Price_INR']
                dist = supplier['Distance']
                ship_rate = 0.75

                max_affordable = int(
                    target_row['Budget_INR'] //
                    (unit_price + dist * ship_rate)
                )

                # FIXED SAFE VALUE (prevents Streamlit error)
                default_qty = min(max_affordable, supplier['StockLevel'], 5)

                c1.write(f"### Source: {supplier['WarehouseID']}")
                c1.write(f"Stock: {supplier['StockLevel']}")
                c1.write(f"Distance: {dist} km")

                qty = c2.number_input(
                    f"Qty from {supplier['WarehouseID']}",
                    min_value=0,
                    max_value=int(supplier['StockLevel']),
                    value=int(default_qty),
                    key=f"qty_{idx}"
                )

                prod_cost = qty * unit_price
                trans_cost = int(qty * dist * ship_rate)
                total_cost = prod_cost + trans_cost

                c2.write(f"Product: ₹{prod_cost:,}")
                c2.write(f"Freight: ₹{trans_cost:,}")
                c2.write(f"Total: ₹{total_cost:,}")

                if c3.button("Confirm", key=f"btn_{idx}"):

                    if qty > 0 and total_cost <= target_row['Budget_INR']:

                        st.session_state.df.loc[
                            st.session_state.df['ProductID'] == target_sku,
                            'StockLevel'
                        ] += qty

                        st.session_state.df.loc[
                            st.session_state.df['ProductID'] == target_sku,
                            'Budget_INR'
                        ] -= total_cost

                        st.session_state.df.loc[
                            supplier.name,
                            'StockLevel'
                        ] -= qty

                        st.session_state.df.loc[
                            supplier.name,
                            'Budget_INR'
                        ] += prod_cost

                        st.session_state.transaction_history.append({
                            "sku": target_sku,
                            "from": supplier['WarehouseID'],
                            "to": target_row['WarehouseID'],
                            "qty": qty,
                            "cost": total_cost,
                            "dist": dist
                        })

                        save_data(st.session_state.df)

                        st.success("Transaction Completed")
                        st.rerun()

                    else:
                        st.error("Invalid / Insufficient Budget")

# =========================
# 7. CATEGORY LEDGER (FIXED + HIGHLIGHT)
# =========================
st.write("---")
st.subheader("📋 Category Wise Ledger")

for cat in df['Category'].unique():

    st.markdown(f"### 🏷️ {cat}")

    cat_df = df[df['Category'] == cat].copy()

    critical = cat_df[(cat_df['StockLevel'] < 10) & (cat_df['Budget_INR'] < 40000)]
    warning = cat_df[(cat_df['StockLevel'] < 10)]

    if not critical.empty:
        st.error(f"CRITICAL RISK: {len(critical)} nodes")
    elif not warning.empty:
        st.warning(f"LOW STOCK: {len(warning)} nodes")

    def highlight(row):
        if row['StockLevel'] < 10:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)

    st.dataframe(
        cat_df.style.apply(highlight, axis=1),
        use_container_width=True
    )

# =========================
# 8. TRANSACTION LOG
# =========================
if st.session_state.transaction_history:

    st.write("---")
    st.subheader("📑 Transaction Audit Log")

    for tx in reversed(st.session_state.transaction_history):
        with st.expander(f"{tx['qty']} units | {tx['from']} → {tx['to']}"):
            st.write(tx)
