import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import requests
import time
import struct
import streamlit_authenticator as stauth

# =========================
# 1. SETUP
# =========================
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Strategic Supply Chain", layout="wide")

DB_FILE = "supplychain.db"
CSV_FILE = "orders.csv"

# =========================
# 2. AUTHENTICATION
# =========================
hashed_passwords = stauth.Hasher(["admin123", "analyst123", "viewer123"]).generate()

credentials = {
    "usernames": {
        "admin": {
            "name": "Admin User",
            "password": hashed_passwords[0],
            "role": "admin"
        },
        "analyst": {
            "name": "Analyst User",
            "password": hashed_passwords[1],
            "role": "analyst"
        },
        "viewer": {
            "name": "Viewer User",
            "password": hashed_passwords[2],
            "role": "viewer"
        }
    }
}

cookie_config = {
    "name":     "supplychain_cookie",
    "key":      "supplychain_secret_key_2024",
    "expiry_days": 1
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_config["name"],
    cookie_config["key"],
    cookie_config["expiry_days"]
)

login_result = authenticator.login(location="main")

if login_result is not None:
    name, authentication_status, username = login_result
else:
    name, authentication_status, username = None, None, None

if authentication_status is False:
    st.error("Incorrect username or password")
    st.stop()

if authentication_status is None:
    st.warning("Please enter your username and password")
    st.info("Demo credentials — Admin: `admin/admin123` | Analyst: `analyst/analyst123` | Viewer: `viewer/viewer123`")
    st.stop()

# Get role
user_role = credentials["usernames"][username]["role"]

st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

col_user1, col_user2 = st.columns([8, 1])
with col_user1:
    if user_role == "admin":
        st.success(f"👑 Logged in as **{name}** — Role: `Admin` (Full Access)")
    elif user_role == "analyst":
        st.info(f"📊 Logged in as **{name}** — Role: `Analyst` (Read + Forecast)")
    else:
        st.warning(f"👁️ Logged in as **{name}** — Role: `Viewer` (Read Only)")
with col_user2:
    authenticator.logout(location="main")

# =========================
# 3. CITY COORDINATES
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
    'Mumbai':    {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150,  'Chennai': 1300, 'Kolkata': 1900},
    'Delhi':     {'Mumbai': 1400,'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000,'Delhi': 2100,     'Pune': 850,  'Chennai': 350,  'Kolkata': 1800},
    'Pune':      {'Mumbai': 150, 'Delhi': 1450,     'Bangalore': 850,'Chennai': 1200,'Kolkata': 1850},
    'Chennai':   {'Mumbai': 1300,'Delhi': 2200,     'Bangalore': 350,'Pune': 1200,  'Kolkata': 1600}
}

# =========================
# 4. OSRM REAL DISTANCE API
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
# 5. SQLITE SETUP
# =========================
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def create_table():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS warehouse_data (
            ProductID      TEXT,
            StockLevel     INTEGER,
            WarehouseID    TEXT,
            Category       TEXT,
            Budget_INR     INTEGER,
            Unit_Price_INR INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT,
            sku              TEXT,
            from_warehouse   TEXT,
            to_warehouse     TEXT,
            qty              INTEGER,
            unit_price       INTEGER,
            freight_cost     INTEGER,
            total_cost       INTEGER,
            from_stock_after INTEGER,
            to_stock_after   INTEGER,
            from_budget_after INTEGER,
            to_budget_after  INTEGER
        )
    """)
    conn.commit()
    conn.close()

def load_csv_to_db():
    if not os.path.exists(CSV_FILE):
        return
    df = pd.read_csv(CSV_FILE)
    df.rename(columns={
        'SKU':          'ProductID',
        'Stock levels': 'StockLevel',
        'Location':     'WarehouseID'
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
    df   = pd.read_sql("SELECT * FROM warehouse_data", conn)
    conn.close()
    return df

def save_data(df):
    conn = get_conn()
    df.to_sql("warehouse_data", conn, if_exists="replace", index=False)
    conn.close()

def save_transaction(sku, from_wh, to_wh, qty, unit_price, freight, total,
                     from_stock_after, to_stock_after, from_budget_after, to_budget_after):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (
            timestamp, sku, from_warehouse, to_warehouse,
            qty, unit_price, freight_cost, total_cost,
            from_stock_after, to_stock_after,
            from_budget_after, to_budget_after
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        sku, from_wh, to_wh,
        int(qty), int(unit_price), int(freight), int(total),
        int(from_stock_after), int(to_stock_after),
        int(from_budget_after), int(to_budget_after)
    ))
    conn.commit()
    conn.close()

def safe_int(val):
    if isinstance(val, bytes):
        length = len(val)
        fmt    = {1: 'b', 2: '<h', 4: '<i', 8: '<q'}.get(length)
        if fmt:
            return struct.unpack(fmt, val)[0]
        return int.from_bytes(val, byteorder='little', signed=True)
    try:
        return int(val)
    except Exception:
        return 0

def load_transactions():
    conn = get_conn()
    try:
        df = pd.read_sql("SELECT * FROM transactions ORDER BY id DESC", conn)
        for col in ['id','qty','unit_price','freight_cost','total_cost',
                    'from_stock_after','to_stock_after','from_budget_after','to_budget_after']:
            if col in df.columns:
                df[col] = df[col].apply(safe_int)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

# =========================
# 6. INIT DB
# =========================
create_table()
conn_test = get_conn()
cursor    = conn_test.cursor()
cursor.execute("SELECT COUNT(*) FROM warehouse_data")
count = cursor.fetchone()[0]
conn_test.close()
if count == 0:
    load_csv_to_db()

# =========================
# 7. SESSION STATE
# =========================
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

df = st.session_state.df

# =========================
# 8. DYNAMIC DATA REFRESH
# =========================
st.write("---")
col_refresh1, col_refresh2, col_refresh3 = st.columns([2, 1, 1])

with col_refresh1:
    auto_refresh = st.toggle("🔄 Auto Refresh (every 60s)", value=False)
with col_refresh2:
    if st.button("🔃 Refresh Now"):
        st.session_state.df    = load_data()
        st.session_state.last_refresh = time.time()
        st.rerun()
with col_refresh3:
    elapsed = int(time.time() - st.session_state.last_refresh)
    st.caption(f"Last refreshed: {elapsed}s ago")

if auto_refresh:
    if time.time() - st.session_state.last_refresh > 60:
        st.session_state.df    = load_data()
        st.session_state.last_refresh = time.time()
        st.rerun()
    else:
        remaining = int(60 - (time.time() - st.session_state.last_refresh))
        st.caption(f"⏱ Next auto-refresh in {remaining}s")
        time.sleep(1)
        st.rerun()

df = st.session_state.df

# =========================
# 9. RISK SCORE ENGINE + AUTO REORDER
# =========================
def compute_risk(row):
    stock_risk    = max(0, 100 - row['StockLevel'] * 5)
    budget_risk   = max(0, 100 - row['Budget_INR'] / 5000)
    distance_risk = np.mean([
        get_distance(row['WarehouseID'], w) for w in df['WarehouseID'].unique()
    ]) / 50
    score = 0.5 * stock_risk + 0.3 * budget_risk + 0.2 * distance_risk
    return min(100, int(score))

def explain_risk(row):
    stock_risk    = max(0, 100 - row['StockLevel'] * 5)
    budget_risk   = max(0, 100 - row['Budget_INR'] / 5000)
    distance_risk = np.mean([
        get_distance(row['WarehouseID'], w) for w in df['WarehouseID'].unique()
    ]) / 50
    stock_contrib  = int(0.5 * stock_risk)
    budget_contrib = int(0.3 * budget_risk)
    dist_contrib   = int(0.2 * distance_risk)
    total          = min(100, stock_contrib + budget_contrib + dist_contrib)
    lines = [
        f"**Total Risk Score: {total}/100**",
        f"- 📦 Stock shortage contributes **{stock_contrib} pts** (stock level: {row['StockLevel']})",
        f"- 💰 Budget stress contributes **{budget_contrib} pts** (budget: ₹{int(row['Budget_INR'])})",
        f"- 🗺️ Network distance contributes **{dist_contrib} pts** (avg road distance from warehouse)",
    ]
    if stock_risk    > 60: lines.append("⚠️ *Low stock is the primary driver — consider reordering soon.*")
    if budget_risk   > 60: lines.append("⚠️ *Budget is critically low — replenishment capacity at risk.*")
    if distance_risk > 60: lines.append("⚠️ *This warehouse is far from the network — freight costs will be high.*")
    if total         < 30: lines.append("✅ *This warehouse is healthy across all dimensions.*")
    return "\n".join(lines)

df['RiskScore'] = df.apply(compute_risk, axis=1)

def auto_reorder(df):
    suggestions = []
    for _, row in df.iterrows():
        if row['RiskScore'] > 60:
            suppliers = df[
                (df['WarehouseID'] != row['WarehouseID']) &
                (df['StockLevel']  > 10)
            ]
            if not suppliers.empty:
                best = suppliers.sort_values('StockLevel', ascending=False).iloc[0]
                qty  = min(20, int(best['StockLevel'] * 0.1))
                suggestions.append(
                    f"{row['WarehouseID']} should request {qty} units from {best['WarehouseID']}"
                )
    return suggestions

reorder_plan = auto_reorder(df)

# =========================
# 10. DEMAND FORECASTING ENGINE
# =========================
def build_demand_series(sku):
    txn_df = load_transactions()
    if not txn_df.empty and 'sku' in txn_df.columns:
        sku_txns = txn_df[txn_df['sku'] == sku].copy()
        if len(sku_txns) >= 3:
            sku_txns['date'] = pd.to_datetime(sku_txns['timestamp']).dt.date
            daily            = sku_txns.groupby('date')['qty'].sum().reset_index()
            daily.columns    = ['date', 'demand']
            daily            = daily.sort_values('date')
            return daily['demand'].tolist(), "real"
    seed      = sum(ord(c) for c in sku)
    rng       = np.random.default_rng(seed)
    base      = rng.integers(5, 20)
    synthetic = [max(0, int(base + rng.normal(0, 3))) for _ in range(14)]
    return synthetic, "synthetic"

def moving_average_forecast(series, window=3, steps=5):
    series   = list(series)
    forecast = []
    for _ in range(steps):
        avg = np.mean(series[-window:])
        forecast.append(round(avg, 2))
        series.append(avg)
    return forecast

def exponential_smoothing_forecast(series, alpha=0.3, steps=5):
    series   = list(series)
    smoothed = [series[0]]
    for val in series[1:]:
        smoothed.append(alpha * val + (1 - alpha) * smoothed[-1])
    forecast = []
    last     = smoothed[-1]
    for _ in range(steps):
        last = alpha * last + (1 - alpha) * last
        forecast.append(round(last, 2))
    return forecast

def linear_regression_forecast(series, steps=5):
    from sklearn.linear_model import LinearRegression
    series = list(series)
    X      = np.arange(len(series)).reshape(-1, 1)
    y      = np.array(series)
    model  = LinearRegression()
    model.fit(X, y)
    future = np.arange(len(series), len(series) + steps).reshape(-1, 1)
    preds  = model.predict(future)
    return [round(max(0, p), 2) for p in preds], model.coef_[0], model.intercept_

def days_until_stockout(current_stock, daily_demand_forecast):
    stock = current_stock
    for i, demand in enumerate(daily_demand_forecast):
        stock -= demand
        if stock <= 0:
            return i + 1
    return None

# =========================
# 11. METRICS
# =========================
m1, m2, m3 = st.columns(3)
m1.metric("Network Liquidity",     f"₹{df['Budget_INR'].sum():,}")
m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")
m3.metric("Transactions",          len(load_transactions()))

# =========================
# 12. AUTO REORDER DISPLAY
# =========================
st.write("---")
st.subheader("🔁 Auto Reorder AI System")
if reorder_plan:
    for r in reorder_plan:
        st.info(r)
else:
    st.success("All warehouses are healthy")

# =========================
# 13. EXPLAINABLE RISK TABLE
# =========================
st.write("---")
st.subheader("🧠 Explainable Risk Score")

risk_df = df[['ProductID','WarehouseID','StockLevel','Budget_INR','RiskScore']].copy()
risk_df = risk_df.sort_values('RiskScore', ascending=False).reset_index(drop=True)

for _, row in risk_df.head(10).iterrows():
    color = "🔴" if row['RiskScore'] > 60 else ("🟡" if row['RiskScore'] > 30 else "🟢")
    with st.expander(f"{color} {row['ProductID']} — {row['WarehouseID']} | Risk: {row['RiskScore']}/100"):
        full_row = df[df['ProductID'] == row['ProductID']].iloc[0]
        st.markdown(explain_risk(full_row))

# =========================
# 14. DEMAND FORECASTING SECTION
# =========================
st.write("---")
st.subheader("📈 Demand Forecasting & Stockout Prediction")
st.caption(
    "Uses **Moving Average**, **Exponential Smoothing**, and **Linear Regression** "
    "on transaction history to forecast daily demand and predict stockouts."
)

all_skus_list = sorted(df['ProductID'].unique().tolist())
fc_col1, fc_col2, fc_col3 = st.columns([2, 1, 1])

with fc_col1:
    selected_sku = st.selectbox("Select SKU to Forecast", all_skus_list, key="fc_sku")
with fc_col2:
    method = st.selectbox(
        "Forecasting Method",
        ["All Three", "Moving Average", "Exponential Smoothing", "Linear Regression"],
        key="fc_method"
    )
with fc_col3:
    forecast_days = st.slider("Forecast Days", min_value=3, max_value=14, value=7, key="fc_days")

if selected_sku:
    sku_row       = df[df['ProductID'] == selected_sku].iloc[0]
    current_stock = int(sku_row['StockLevel'])
    series, data_type = build_demand_series(selected_sku)

    if data_type == "synthetic":
        st.warning("⚠️ Insufficient real transaction data. Showing forecast on **synthetic baseline** for demonstration.")
    else:
        st.success(f"✅ Forecasting from **{len(series)} real transaction data points**.")

    ma_forecast              = moving_average_forecast(series, window=3, steps=forecast_days)
    es_forecast              = exponential_smoothing_forecast(series, alpha=0.3, steps=forecast_days)
    lr_forecast, coef, intercept = linear_regression_forecast(series, steps=forecast_days)

    history_days = list(range(1, len(series) + 1))
    future_days  = list(range(len(series) + 1, len(series) + forecast_days + 1))

    import altair as alt

    history_series = pd.DataFrame({"Day": history_days, "Actual Demand": series})
    ma_series      = pd.DataFrame({"Day": future_days,  "Moving Avg (MA)": ma_forecast})
    es_series      = pd.DataFrame({"Day": future_days,  "Exp Smoothing (ES)": es_forecast})
    lr_series      = pd.DataFrame({"Day": future_days,  "Linear Regression (LR)": lr_forecast})

    base_chart  = alt.Chart(history_series).mark_line(color='steelblue', strokeWidth=2).encode(
        x=alt.X('Day:Q', title='Day'), y=alt.Y('Actual Demand:Q', title='Units'),
        tooltip=['Day','Actual Demand']
    )
    point_chart = alt.Chart(history_series).mark_point(color='steelblue', filled=True, size=60).encode(
        x='Day:Q', y='Actual Demand:Q', tooltip=['Day','Actual Demand']
    )
    charts = [base_chart + point_chart]

    if method in ["All Three", "Moving Average"]:
        charts.append(
            alt.Chart(ma_series).mark_line(color='orange', strokeDash=[6,3], strokeWidth=2).encode(
                x='Day:Q', y='Moving Avg (MA):Q', tooltip=['Day','Moving Avg (MA)']
            ) +
            alt.Chart(ma_series).mark_point(color='orange', filled=True, size=60).encode(
                x='Day:Q', y='Moving Avg (MA):Q'
            )
        )

    if method in ["All Three", "Exponential Smoothing"]:
        charts.append(
            alt.Chart(es_series).mark_line(color='green', strokeDash=[4,2], strokeWidth=2).encode(
                x='Day:Q', y='Exp Smoothing (ES):Q', tooltip=['Day','Exp Smoothing (ES)']
            ) +
            alt.Chart(es_series).mark_point(color='green', filled=True, size=60).encode(
                x='Day:Q', y='Exp Smoothing (ES):Q'
            )
        )

    if method in ["All Three", "Linear Regression"]:
        charts.append(
            alt.Chart(lr_series).mark_line(color='red', strokeDash=[3,2], strokeWidth=2).encode(
                x='Day:Q', y='Linear Regression (LR):Q', tooltip=['Day','Linear Regression (LR)']
            ) +
            alt.Chart(lr_series).mark_point(color='red', filled=True, size=60).encode(
                x='Day:Q', y='Linear Regression (LR):Q'
            )
        )

    st.altair_chart(
        alt.layer(*charts).properties(
            title=f"Demand Forecast — {selected_sku}", height=350
        ).configure_title(fontSize=15),
        use_container_width=True
    )

    if method in ["All Three", "Linear Regression"]:
        trend = "📈 Upward" if coef > 0 else "📉 Downward"
        st.caption(f"LR Trend: **{trend}** (slope: {round(coef, 3)} units/day | intercept: {round(intercept, 2)})")

    st.markdown("#### 🚨 Stockout Prediction")
    so_cols = st.columns(4)
    so_cols[0].metric("Current Stock", f"{current_stock} units")

    if method in ["All Three", "Moving Average"]:
        days_ma = days_until_stockout(current_stock, ma_forecast)
        so_cols[1].metric(
            "MA Stockout In",
            f"{days_ma} day(s)" if days_ma else "Safe ✅",
            delta="⚠️ Reorder" if days_ma and days_ma <= 3 else None,
            delta_color="inverse"
        )
    if method in ["All Three", "Exponential Smoothing"]:
        days_es = days_until_stockout(current_stock, es_forecast)
        so_cols[2].metric(
            "ES Stockout In",
            f"{days_es} day(s)" if days_es else "Safe ✅",
            delta="⚠️ Reorder" if days_es and days_es <= 3 else None,
            delta_color="inverse"
        )
    if method in ["All Three", "Linear Regression"]:
        days_lr = days_until_stockout(current_stock, lr_forecast)
        so_cols[3].metric(
            "LR Stockout In",
            f"{days_lr} day(s)" if days_lr else "Safe ✅",
            delta="⚠️ Reorder" if days_lr and days_lr <= 3 else None,
            delta_color="inverse"
        )

    with st.expander("📊 View Forecast Numbers"):
        forecast_table = pd.DataFrame({"Day": future_days})
        if method in ["All Three", "Moving Average"]:
            forecast_table["Moving Avg"]         = ma_forecast
        if method in ["All Three", "Exponential Smoothing"]:
            forecast_table["Exp Smoothing"]       = es_forecast
        if method in ["All Three", "Linear Regression"]:
            forecast_table["Linear Regression"]   = lr_forecast
        st.dataframe(forecast_table, use_container_width=True)

# =========================
# 15. SEARCH + TRANSACTIONS (admin + analyst only)
# =========================
st.write("---")
st.subheader("🔍 Strategic Sourcing")

if user_role == "viewer":
    st.warning("👁️ Viewer role — read only. Contact admin to perform transactions.")
else:
    target_sku = st.text_input("Search SKU").upper()

    if target_sku:
        sku_rows = df[df['ProductID'] == target_sku]
        if not sku_rows.empty:
            target_row = sku_rows.iloc[0]
            st.info(f"Warehouse: {target_row['WarehouseID']} | Budget: ₹{target_row['Budget_INR']}")

            suppliers = df[
                (df['WarehouseID'] != target_row['WarehouseID']) &
                (df['StockLevel']  > 0)
            ].copy()
            suppliers['Distance'] = suppliers['WarehouseID'].apply(
                lambda x: get_distance(target_row['WarehouseID'], x)
            )
            suppliers = suppliers.sort_values(by='Distance').head(2)

            for idx, s in suppliers.iterrows():
                with st.container(border=True):
                    c1, c2, c3    = st.columns([2, 1, 1])
                    unit_price    = target_row['Unit_Price_INR']
                    dist          = s['Distance']
                    ship_rate     = 0.75
                    max_affordable = int(target_row['Budget_INR'] // (unit_price + dist * ship_rate))
                    default_qty   = min(max_affordable, s['StockLevel'], 5)

                    c1.write(f"### {s['WarehouseID']}")
                    c1.write(f"Stock: {s['StockLevel']}")
                    c1.write(f"Distance: {dist} km (OSRM)")

                    safe_max     = max(0, int(s['StockLevel']))
                    safe_default = min(int(default_qty), safe_max) if safe_max > 0 else 0

                    qty     = c2.number_input("Qty", min_value=0, max_value=safe_max, value=safe_default, key=f"q_{idx}")
                    prod    = qty * unit_price
                    freight = int(qty * dist * ship_rate)
                    total   = prod + freight
                    c2.write(f"Product ₹{prod}")
                    c2.write(f"Freight ₹{freight}")
                    c2.write(f"Total ₹{total}")

                    confirm_allowed = (user_role == "admin")
                    if not confirm_allowed:
                        c3.info("Analyst can view but only admin can confirm")

                    if confirm_allowed and c3.button("Confirm", key=f"b_{idx}"):
                        if qty > 0 and total <= target_row['Budget_INR']:
                            st.session_state.df.loc[st.session_state.df['ProductID'] == target_sku, 'StockLevel'] += qty
                            st.session_state.df.loc[st.session_state.df['ProductID'] == target_sku, 'Budget_INR'] -= total
                            st.session_state.df.loc[s.name, 'StockLevel'] -= qty
                            st.session_state.df.loc[s.name, 'Budget_INR'] += prod

                            new_to_stock    = int(st.session_state.df.loc[st.session_state.df['ProductID'] == target_sku, 'StockLevel'].values[0])
                            new_to_budget   = int(st.session_state.df.loc[st.session_state.df['ProductID'] == target_sku, 'Budget_INR'].values[0])
                            new_from_stock  = int(st.session_state.df.loc[s.name, 'StockLevel'])
                            new_from_budget = int(st.session_state.df.loc[s.name, 'Budget_INR'])

                            save_data(st.session_state.df)
                            save_transaction(
                                sku=target_sku, from_wh=s['WarehouseID'],
                                to_wh=target_row['WarehouseID'], qty=qty,
                                unit_price=unit_price, freight=freight, total=total,
                                from_stock_after=new_from_stock, to_stock_after=new_to_stock,
                                from_budget_after=new_from_budget, to_budget_after=new_to_budget
                            )
                            st.success("Done")
                            st.rerun()

# =========================
# 16. TRANSACTION HISTORY LEDGER
# =========================
st.write("---")
st.subheader("📒 Transaction History Ledger")

txn_df = load_transactions()

if txn_df.empty:
    st.info("No transactions yet.")
else:
    st.caption(f"Total transactions recorded: {len(txn_df)}")

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        all_skus   = ["All"] + sorted(txn_df['sku'].unique().tolist())
        filter_sku = st.selectbox("Filter by SKU", all_skus)
    with filter_col2:
        all_wh    = ["All"] + sorted(
            pd.concat([txn_df['from_warehouse'], txn_df['to_warehouse']]).unique().tolist()
        )
        filter_wh = st.selectbox("Filter by Warehouse", all_wh)

    filtered = txn_df.copy()
    if filter_sku != "All":
        filtered = filtered[filtered['sku'] == filter_sku]
    if filter_wh != "All":
        filtered = filtered[
            (filtered['from_warehouse'] == filter_wh) |
            (filtered['to_warehouse']   == filter_wh)
        ]

    st.caption(f"Showing {len(filtered)} transaction(s)")

    for _, txn in filtered.iterrows():
        txn_id          = int(txn['id'])
        txn_qty         = int(txn['qty'])
        txn_total       = int(txn['total_cost'])
        txn_unit        = int(txn['unit_price'])
        txn_freight     = int(txn['freight_cost'])
        txn_from_stock  = int(txn['from_stock_after'])
        txn_to_stock    = int(txn['to_stock_after'])
        txn_from_budget = int(txn['from_budget_after'])
        txn_to_budget   = int(txn['to_budget_after'])

        label = (
            f"🧾 #{txn_id} | {txn['timestamp']} | "
            f"{txn['sku']} | {txn['from_warehouse']} → {txn['to_warehouse']} | "
            f"Qty: {txn_qty} | ₹{txn_total:,}"
        )
        with st.expander(label):
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**📤 Sender Warehouse**")
                st.markdown(f"- Warehouse: `{txn['from_warehouse']}`")
                st.markdown(f"- Units dispatched: `{txn_qty}`")
                st.markdown(f"- Stock after: `{txn_from_stock}`")
                st.markdown(f"- Budget after: `₹{txn_from_budget:,}`")
            with d2:
                st.markdown("**📥 Receiver Warehouse**")
                st.markdown(f"- Warehouse: `{txn['to_warehouse']}`")
                st.markdown(f"- Units received: `{txn_qty}`")
                st.markdown(f"- Stock after: `{txn_to_stock}`")
                st.markdown(f"- Budget after: `₹{txn_to_budget:,}`")
            st.markdown("---")
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Unit Price",   f"₹{txn_unit:,}")
            b2.metric("Freight Cost", f"₹{txn_freight:,}")
            b3.metric("Product Cost", f"₹{txn_qty * txn_unit:,}")
            b4.metric("Total Cost",   f"₹{txn_total:,}")

# =========================
# 17. CATEGORY LEDGER
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
