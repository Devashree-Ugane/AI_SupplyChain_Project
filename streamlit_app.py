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

def get_distance(c1, c2):
    if c1 == c2:
        return 0
    return DISTANCE_MAP.get(c1, {}).get(c2, 800)

# =========================
# 3. SQLITE SETUP
# =========================
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def create_table():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
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
    """Run only once when DB is first created"""
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
            len(df)
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
# 4. INIT DB (SAFE)
# =========================
create_table()

# IMPORTANT FIX:
# Always migrate if DB is empty (not only file check)
conn_test = get_conn()
cursor = conn_test.cursor()
cursor.execute("SELECT COUNT(*) FROM warehouse_data")
count = cursor.fetchone()[0]
conn_test.close()

if count == 0:
    load_csv_to_db()

# =========================
# 5. SESSION STATE
# =========================
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

df = st.session_state.df

# =========================
# 6. METRICS
# =========================
m1, m2, m3 = st.columns(3)

m1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
m3.metric("Transactions", len(st.session_state.transaction_history))

# =========================
# 7. SEARCH + TRANSACTIONS
# =========================
st.write("---")
st.subheader("🔍 Strategic Sourcing")

target_sku = st.text_input("Search SKU").upper()

if target_sku:

    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:

        target_row = sku_rows.iloc[0]

        st.info(f"Warehouse: {target_row['WarehouseID']} | Budget: ₹{target_row['Budget_INR']}")

        suppliers = df[
            (df['WarehouseID'] != target_row['WarehouseID']) &
            (df['StockLevel'] > 0)
        ].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(
            lambda x: get_distance(target_row['WarehouseID'], x)
        )

        suppliers = suppliers.sort_values(by='Distance').head(2)

        for idx, s in suppliers.iterrows():

            with st.container(border=True):

                c1, c2, c3 = st.columns([2, 1, 1])

                unit_price = target_row['Unit_Price_INR']
                dist = s['Distance']
                ship_rate = 0.75

                max_affordable = int(
                    target_row['Budget_INR'] //
                    (unit_price + dist * ship_rate)
                )

                default_qty = min(max_affordable, s['StockLevel'], 5)

                c1.write(f"### {s['WarehouseID']}")
                c1.write(f"Stock: {s['StockLevel']}")
                c1.write(f"Distance: {dist} km")

                # FIX: prevent Streamlit max error
                safe_max = max(0, int(s['StockLevel']))
                safe_default = min(int(default_qty), safe_max) if safe_max > 0 else 0

                qty = c2.number_input(
                    "Qty",
                    min_value=0,
                    max_value=safe_max,
                    value=safe_default,
                    key=f"q_{idx}"
                )

                prod = qty * unit_price
                freight = int(qty * dist * ship_rate)
                total = prod + freight

                c2.write(f"Product ₹{prod}")
                c2.write(f"Freight ₹{freight}")
                c2.write(f"Total ₹{total}")

                if c3.button("Confirm", key=f"b_{idx}"):

                    if qty > 0 and total <= target_row['Budget_INR']:

                        st.session_state.df.loc[
                            st.session_state.df['ProductID'] == target_sku,
                            'StockLevel'
                        ] += qty

                        st.session_state.df.loc[
                            st.session_state.df['ProductID'] == target_sku,
                            'Budget_INR'
                        ] -= total

                        st.session_state.df.loc[s.name, 'StockLevel'] -= qty
                        st.session_state.df.loc[s.name, 'Budget_INR'] += prod

                        st.session_state.transaction_history.append({
                            "sku": target_sku,
                            "from": s['WarehouseID'],
                            "qty": qty,
                            "cost": total
                        })

                        save_data(st.session_state.df)
                        st.success("Done")
                        st.rerun()

# =========================
# 8. CATEGORY LEDGER (FIXED + SAFE HIGHLIGHT)
# =========================
st.write("---")
st.subheader("📋 Category Ledger")

for cat in df['Category'].unique():

    st.markdown(f"### {cat}")

    cat_df = df[df['Category'] == cat]

    def highlight(row):
        if row['StockLevel'] < 10:
            return ['background-color: rgba(255, 0, 0, 0.12)'] * len(row)
        return [''] * len(row)

    styled = cat_df.style.apply(highlight, axis=1)

    st.dataframe(styled, use_container_width=True)
