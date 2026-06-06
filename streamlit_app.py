import warnings

import os

import streamlit as st

import pandas as pd

import numpy as np



# 1. Setup

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Strategic Supply Chain", layout="wide")

st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")



# 2. CORE DATA ENGINE & LOGISTICS MAP

CSV_FILE = "orders.csv"



# Real-world Distance Matrix for India Hubs

DISTANCE_MAP = {

    'Mumbai': {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150, 'Chennai': 1300, 'Kolkata': 1900},

    'Delhi': {'Mumbai': 1400, 'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},

    'Bangalore': {'Mumbai': 1000, 'Delhi': 2100, 'Pune': 850, 'Chennai': 350, 'Kolkata': 1800},

    'Pune': {'Mumbai': 150, 'Delhi': 1450, 'Bangalore': 850, 'Chennai': 1200, 'Kolkata': 1850},

    'Chennai': {'Mumbai': 1300, 'Delhi': 2200, 'Bangalore': 350, 'Pune': 1200, 'Kolkata': 1600}

}



def get_distance(city1, city2):

    if city1 == city2: return 0

    return DISTANCE_MAP.get(city1, {}).get(city2, 800)



def process_dataframe(df):

    df.rename(columns={'SKU': 'ProductID', 'Stock levels': 'StockLevel', 'Location': 'WarehouseID'}, inplace=True)

    if 'Category' not in df.columns:

        df['Category'] = [np.random.choice(['Haircare', 'Skincare', 'Wellness', 'Cosmetics']) for _ in range(len(df))]

    if 'Budget_INR' not in df.columns:

        df['Budget_INR'] = np.random.randint(80000, 300000, len(df))

    if 'Unit_Price_INR' not in df.columns:

        df['Unit_Price_INR'] = np.random.randint(2000, 8000, len(df))

    return df



def save_data(df):

    df.to_csv(CSV_FILE, index=False)



# Load State

if 'df' not in st.session_state:

    if os.path.exists(CSV_FILE):

        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))

    else:

        st.error("Critical Error: orders.csv not found.")

        st.stop()



if 'transaction_history' not in st.session_state:

    st.session_state.transaction_history = []



df = st.session_state.df



# 3. TOP METRICS

m1, m2, m3 = st.columns(3)

m1.metric("Network Liquidity", f"₹{df['Budget_INR'].sum():,}")

m2.metric("Inventory Asset Value", f"₹{(df['StockLevel'] * df['Unit_Price_INR']).sum():,}")

m3.metric("Settled Transactions", len(st.session_state.transaction_history))



# 4. SEARCH & TRANSACTION INTERFACE

st.write("---")

st.subheader("🔍 Strategic Sourcing & Landed Cost Optimization")



target_sku = st.text_input("Search SKU to optimize (e.g., SKU1):").upper()



if target_sku:

    sku_rows = df[df['ProductID'] == target_sku]

    if not sku_rows.empty:

        target_row = sku_rows.loc[sku_rows['StockLevel'].idxmin()]

        st.info(f"**Target Node:** {target_row['WarehouseID']} | **Budget:** ₹{target_row['Budget_INR']:,} | **Stock:** {target_row['StockLevel']}")

        

        # Sourcing Logic: Rank by Distance

        suppliers = df[(df['WarehouseID'] != target_row['WarehouseID']) & (df['StockLevel'] > 5)].copy()

        suppliers['Distance'] = suppliers['WarehouseID'].apply(lambda x: get_distance(target_row['WarehouseID'], x))

        suppliers = suppliers.sort_values(by='Distance').head(2)

        

        for idx, supplier in suppliers.iterrows():

            with st.container(border=True):

                c_info, c_input, c_exec = st.columns([2, 1, 1])

                

                unit_price = target_row['Unit_Price_INR']

                dist = supplier['Distance']

                ship_rate = 0.75 # ₹0.75 per km per unit

                max_affordable = int(target_row['Budget_INR'] // (unit_price + (dist * ship_rate)))

                

                with c_info:

                    st.write(f"### Source: {supplier['WarehouseID']}")

                    st.write(f"**Surplus Available:** {supplier['StockLevel']} units")

                    st.write(f"**Distance:** {dist} km ({'Local' if dist < 300 else 'Interstate'})")

                    st.write(f"**Max Affordable:** {max_affordable} units (Inc. Freight)")



                with c_input:

                    move_qty = st.number_input(f"Qty from {supplier['WarehouseID']}:", 

                                             min_value=0, max_value=int(supplier['StockLevel']), value=min(max_affordable, 10) if max_affordable > 0 else 0, key=f"qty_{idx}")

                    

                    prod_cost = move_qty * unit_price

                    trans_cost = int(move_qty * dist * ship_rate)

                    total_landed_cost = prod_cost + trans_cost

                    

                    st.write(f"Product: ₹{prod_cost:,}")

                    st.write(f"Freight: ₹{trans_cost:,}")

                    st.write(f"**Total Landed:** ₹{total_landed_cost:,}")



                with c_exec:

                    if total_landed_cost > target_row['Budget_INR']:

                        st.error("Insolvent")

                    elif move_qty == 0:

                        st.warning("Adjust Quantity")

                    else:

                        if st.button(f"Confirm & Settle", key=f"btn_{idx}"):

                            # Update Taker

                            st.session_state.df.loc[target_row.name, 'StockLevel'] += move_qty

                            st.session_state.df.loc[target_row.name, 'Budget_INR'] -= total_landed_cost

                            # Update Giver (Product revenue only)

                            st.session_state.df.loc[supplier.name, 'StockLevel'] -= move_qty

                            st.session_state.df.loc[supplier.name, 'Budget_INR'] += prod_cost

                            

                            st.session_state.transaction_history.append({

                                "sku": target_sku, "from": supplier['WarehouseID'], "to": target_row['WarehouseID'],

                                "qty": move_qty, "val": total_landed_cost, "dist": dist,

                                "t_bal": f"₹{target_row['Budget_INR']:,} ➔ ₹{target_row['Budget_INR'] - total_landed_cost:,}",

                                "g_bal": f"₹{supplier['Budget_INR']:,} ➔ ₹{supplier['Budget_INR'] + prod_cost:,}"

                            })

                            save_data(st.session_state.df)

                            st.balloons()

                            st.rerun()



# 5. SEGMENTED TABLES & CATEGORICAL ALERTS

st.write("---")

st.subheader("📋 Segmented Operational Ledgers")



for cat in sorted(df['Category'].unique()):

    st.markdown(f"### 🏷️ {cat}")

    cat_df = df[df['Category'] == cat].sort_values(by='ProductID')

    

    # Restored Alert Logic

    critical_risk = cat_df[(cat_df['StockLevel'] < 10) & (cat_df['Budget_INR'] < 40000)]

    stock_risk = cat_df[(cat_df['StockLevel'] < 10) & (cat_df['Budget_INR'] >= 40000)]

    

    if not critical_risk.empty:

        st.error(f"🔴 **CRITICAL SOLVENCY RISK:** {len(critical_risk)} node(s) cannot afford replenishment.")

        st.caption("📋 *Action: Emergency Budget Request Required.*")

    elif not stock_risk.empty:

        st.warning(f"🟡 **REPLENISHMENT ALERT:** {len(stock_risk)} node(s) low on stock. Use funds to optimize.")

    

    st.dataframe(

        cat_df.style.highlight_min(subset=['StockLevel'], color='#ff4b4b')

        .highlight_max(subset=['Budget_INR'], color='#90ee90'),

        use_container_width=True

    )

    st.write("")



# 6. MINUTE TRANSACTION AUDIT

if st.session_state.transaction_history:

    st.write("---")

    st.subheader("📑 Minute Transaction Details")

    for tx in reversed(st.session_state.transaction_history):

        with st.expander(f"✅ Settled: {tx['qty']} units | {tx['from']} ➔ {tx['to']} ({tx['dist']}km)", expanded=True):

            ca, cb, cc = st.columns(3)

            ca.write(f"**Freight Details:** ₹{tx['val']:,} Total Cost")

            cb.write(f"**Taker Balance:** {tx['t_bal']}")

            cc.write(f"**Giver Balance:** {tx['g_bal']}") 
