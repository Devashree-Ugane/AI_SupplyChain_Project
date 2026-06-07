import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import requests
import random
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
CITY_COORDS = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bangalore": (12.9716, 77.5946),
    "Pune": (18.5204, 73.8567),
    "Chennai": (13.0827, 80.2707)
}

def get_distance(c1, c2):

    if c1 == c2:
        return 0

    try:

        lat1, lon1 = CITY_COORDS[c1]
        lat2, lon2 = CITY_COORDS[c2]

        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )

        response = requests.get(url, timeout=5)

        distance_km = (
            response.json()["routes"][0]["distance"] / 1000
        )

        return round(distance_km)

    except:
        return 800

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
# 4. INIT DB
# =========================
create_table()

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
st.write("---")
st.subheader("🔄 Dynamic Operations Simulator")

if st.button("Simulate New Day"):

    for idx in df.index:

        consumption = random.randint(0, 5)

        df.loc[idx, "StockLevel"] = max(
            0,
            df.loc[idx, "StockLevel"] - consumption
        )

        df.loc[idx, "Budget_INR"] += random.randint(
            -5000,
            10000
        )

    save_data(df)

    st.success("New operational day simulated")

    st.rerun()
# =========================
# 6. RISK SCORE ENGINE + AUTO REORDER (NEW)
# =========================
def compute_risk(row):

    stock_component = max(
        0,
        100 - row['StockLevel'] * 5
    )

    budget_component = max(
        0,
        100 - row['Budget_INR'] / 5000
    )

    distance_component = np.mean([
        get_distance(
            row['WarehouseID'],
            w
        )
        for w in df['WarehouseID'].unique()
    ]) / 50

    score = (
        0.5 * stock_component +
        0.3 * budget_component +
        0.2 * distance_component
    )

    return pd.Series([
        min(100, int(score)),
        int(stock_component),
        int(budget_component),
        int(distance_component)
    ])

df[
    [
        'RiskScore',
        'StockRisk',
        'BudgetRisk',
        'DistanceRisk'
    ]
] = df.apply(
    compute_risk,
    axis=1
)

def auto_reorder(df):
    suggestions = []

    for _, row in df.iterrows():
        if row['RiskScore'] > 60:
            suppliers = df[
                (df['WarehouseID'] != row['WarehouseID']) &
                (df['StockLevel'] > 10)
            ]

            if not suppliers.empty:
                best = suppliers.sort_values('StockLevel', ascending=False).iloc[0]

                qty = min(20, int(best['StockLevel'] * 0.1))

                suggestions.append(
                    f"{row['WarehouseID']} should request {qty} units from {best['WarehouseID']}"
                )

    return suggestions

reorder_plan = auto_reorder(df)

# =========================
# 7. METRICS
# =========================
m1, m2, m3 = st.columns(3)

m1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
m3.metric("Transactions", len(st.session_state.transaction_history))

# =========================
# 8. AUTO REORDER DISPLAY
# =========================
st.write("---")
st.subheader("🔁 Auto Reorder AI System")

if reorder_plan:
    for r in reorder_plan:
        st.info(r)
else:
    st.success("All warehouses are healthy")

# =========================
# 9. SEARCH + TRANSACTIONS
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



st.write("---")
st.subheader("🧠 Explainable AI Risk Analysis")

high_risk = df.sort_values(
    "RiskScore",
    ascending=False
).head(5)

for _, row in high_risk.iterrows():

    st.warning(
        f"""
Warehouse: {row['WarehouseID']}

Risk Score: {row['RiskScore']}/100

Stock Risk Contribution: {row['StockRisk']}

Budget Risk Contribution: {row['BudgetRisk']}

Distance Risk Contribution: {row['DistanceRisk']}
"""
    )

# =========================
# 10. CATEGORY LEDGER
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

    st.dataframe(cat_df.style.apply(highlight, axis=1), use_container_width=True)
