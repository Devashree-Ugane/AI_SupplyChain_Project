import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import requests
import time

# =========================
# 1. SETUP
# =========================
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

DB_FILE = "supplychain.db"
CSV_FILE = "orders.csv"

# =========================
# 2. CITY COORDINATES
# =========================
CITY_COORDS = {
    'Mumbai':    (19.0760, 72.8777),
    'Delhi':     (28.6139, 77.2090),
    'Bangalore': (12.9716, 77.5946),
    'Pune':      (18.5204, 73.8567),
    'Chennai':   (13.0827, 80.2707),
    'Kolkata':   (22.5726, 88.3639),
}

FALLBACK_DISTANCE_MAP = {
    'Mumbai': {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150, 'Chennai': 1300, 'Kolkata': 1900},
    'Delhi': {'Mumbai': 1400, 'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000, 'Delhi': 2100, 'Pune': 850, 'Chennai': 350, 'Kolkata': 1800},
    'Pune': {'Mumbai': 150, 'Delhi': 1450, 'Bangalore': 850, 'Chennai': 1200, 'Kolkata': 1850},
    'Chennai': {'Mumbai': 1300, 'Delhi': 2200, 'Bangalore': 350, 'Pune': 1200, 'Kolkata': 1600}
}

# =========================
# 3. OSRM REAL DISTANCE API
# =========================
@st.cache_data(ttl=86400)
def get_osrm_distance(city1, city2):
    if city1 == city2:
        return 0
    try:
        c1 = CITY_COORDS.get(city1)
        c2 = CITY_COORDS.get(city2)
        if not c1 or not c2:
            return FALLBACK_DISTANCE_MAP.get(city1, {}).get(city2, 800)
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{c1[1]},{c1[0]};{c2[1]},{c2[0]}"
            f"?overview=false"
        )
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("code") == "Ok":
            meters = data["routes"][0]["distance"]
            return int(meters / 1000)
        else:
            return FALLBACK_DISTANCE_MAP.get(city1, {}).get(city2, 800)
    except Exception:
        return FALLBACK_DISTANCE_MAP.get(city1, {}).get(city2, 800)

def get_distance(c1, c2):
    return get_osrm_distance(c1, c2)

# =========================
# 4. SQLITE SETUP
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
            ['Haircare', 'Skincare', 'Wellness', 'Cosmetics'], len(df)
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
# 5. INIT DB
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
# 6. SESSION STATE
# =========================
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

df = st.session_state.df

# =========================
# 7. DYNAMIC DATA REFRESH
# =========================
st.write("---")
col_refresh1, col_refresh2, col_refresh3 = st.columns([2, 1, 1])

with col_refresh1:
    auto_refresh = st.toggle("🔄 Auto Refresh (every 60s)", value=False)

with col_refresh2:
    if st.button("🔃 Refresh Now"):
        st.session_state.df = load_data()
        st.session_state.last_refresh = time.time()
        st.rerun()

with col_refresh3:
    elapsed = int(time.time() - st.session_state.last_refresh)
    st.caption(f"Last refreshed: {elapsed}s ago")

if auto_refresh:
    if time.time() - st.session_state.last_refresh > 60:
        st.session_state.df = load_data()
        st.session_state.last_refresh = time.time()
        st.rerun()
    else:
        remaining = int(60 - (time.time() - st.session_state.last_refresh))
        st.caption(f"⏱ Next auto-refresh in {remaining}s")
        time.sleep(1)
        st.rerun()

df = st.session_state.df

# =========================
# 8. EXPLAINABLE RISK SCORE ENGINE + AUTO REORDER
# =========================
def compute_risk(row):
    stock_risk = max(0, 100 - row['StockLevel'] * 5)
    budget_risk = max(0, 100 - row['Budget_INR'] / 5000)
    distance_risk = np.mean([
        get_distance(row['WarehouseID'], w) for w in df['WarehouseID'].unique()
    ]) / 50

    score = 0.5 * stock_risk + 0.3 * budget_risk + 0.2 * distance_risk
    return min(100, int(score))

def explain_risk(row):
    stock_risk   = max(0, 100 - row['StockLevel'] * 5)
    budget_risk  = max(0, 100 - row['Budget_INR'] / 5000)
    distance_risk = np.mean([
        get_distance(row['WarehouseID'], w) for w in df['WarehouseID'].unique()
    ]) / 50

    stock_contrib   = int(0.5 * stock_risk)
    budget_contrib  = int(0.3 * budget_risk)
    dist_contrib    = int(0.2 * distance_risk)
    total           = min(100, stock_contrib + budget_contrib + dist_contrib)

    lines = [
        f"**Total Risk Score: {total}/100**",
        f"- 📦 Stock shortage contributes **{stock_contrib} pts** (stock level: {row['StockLevel']})",
        f"- 💰 Budget stress contributes **{budget_contrib} pts** (budget: ₹{int(row['Budget_INR'])})",
        f"- 🗺️ Network distance contributes **{dist_contrib} pts** (avg road distance from warehouse)",
    ]

    if stock_risk > 60:
        lines.append("⚠️ *Low stock is the primary driver — consider reordering soon.*")
    if budget_risk > 60:
        lines.append("⚠️ *Budget is critically low — replenishment capacity at risk.*")
    if distance_risk > 60:
        lines.append("⚠️ *This warehouse is far from the network — freight costs will be high.*")
    if total < 30:
        lines.append("✅ *This warehouse is healthy across all dimensions.*")

    return "\n".join(lines)

df['RiskScore'] = df.apply(compute_risk, axis=1)

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
# 9. METRICS
# =========================
m1, m2, m3 = st.columns(3)
m1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")
m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
m3.metric("Transactions", len(st.session_state.transaction_history))

# =========================
# 10. AUTO REORDER DISPLAY
# =========================
st.write("---")
st.subheader("🔁 Auto Reorder AI System")
if reorder_plan:
    for r in reorder_plan:
        st.info(r)
else:
    st.success("All warehouses are healthy")

# =========================
# 11. EXPLAINABLE RISK TABLE
# =========================
st.write("---")
st.subheader("🧠 Explainable Risk Score")

risk_df = df[['ProductID', 'WarehouseID', 'StockLevel', 'Budget_INR', 'RiskScore']].copy()
risk_df = risk_df.sort_values('RiskScore', ascending=False).reset_index(drop=True)

for _, row in risk_df.head(10).iterrows():
    color = "🔴" if row['RiskScore'] > 60 else ("🟡" if row['RiskScore'] > 30 else "🟢")
    with st.expander(f"{color} {row['ProductID']} — {row['WarehouseID']} | Risk: {row['RiskScore']}/100"):
        full_row = df[df['ProductID'] == row['ProductID']].iloc[0]
        st.markdown(explain_risk(full_row))

# =========================
# 12. SEARCH + TRANSACTIONS
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
                    target_row['Budget_INR'] // (unit_price + dist * ship_rate)
                )
                default_qty = min(max_affordable, s['StockLevel'], 5)
                c1.write(f"### {s['WarehouseID']}")
                c1.write(f"Stock: {s['StockLevel']}")
                c1.write(f"Distance: {dist} km (via OSRM road distance)")

                safe_max = max(0, int(s['StockLevel']))
                safe_default = min(int(default_qty), safe_max) if safe_max > 0 else 0

                qty = c2.number_input(
                    "Qty", min_value=0, max_value=safe_max,
                    value=safe_default, key=f"q_{idx}"
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
                            st.session_state.df['ProductID'] == target_sku, 'StockLevel'
                        ] += qty
                        st.session_state.df.loc[
                            st.session_state.df['ProductID'] == target_sku, 'Budget_INR'
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
# 13. CATEGORY LEDGER
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
