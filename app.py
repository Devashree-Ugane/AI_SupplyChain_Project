import warnings
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import faiss
from sentence_transformers import SentenceTransformer
from fpdf import FPDF
import io

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

st.set_page_config(page_title="Strategic Supply Chain", layout="wide")
st.title("🏛️ AI Supply Chain: Logistics, Solvency & Multi-Entity Ledger")

# ── DISTANCE MAP ────────────────────────────────────────────────────────────────
DISTANCE_MAP = {
    'Mumbai':    {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150,  'Chennai': 1300, 'Kolkata': 1900},
    'Delhi':     {'Mumbai': 1400,'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
    'Bangalore': {'Mumbai': 1000,'Delhi': 2100,     'Pune': 850,  'Chennai': 350,  'Kolkata': 1800},
    'Pune':      {'Mumbai': 150, 'Delhi': 1450,     'Bangalore': 850,'Chennai': 1200,'Kolkata': 1850},
    'Chennai':   {'Mumbai': 1300,'Delhi': 2200,     'Bangalore': 350,'Pune': 1200,  'Kolkata': 1600},
    'Kolkata':   {'Mumbai': 1900,'Delhi': 1500,     'Bangalore': 1800,'Chennai': 1600,'Pune': 1850},
}

def get_distance(city1, city2):
    if city1 == city2: return 0
    return DISTANCE_MAP.get(city1, {}).get(city2, 800)

# ── DATA PROCESSING ─────────────────────────────────────────────────────────────
CSV_FILE = "orders.csv"

def process_dataframe(df):
    df.rename(columns={'SKU': 'ProductID', 'Stock levels': 'StockLevel', 'Location': 'WarehouseID'}, inplace=True)
    if 'Category' not in df.columns:
        df['Category'] = [np.random.choice(['Haircare','Skincare','Wellness','Cosmetics']) for _ in range(len(df))]
    if 'Budget_INR' not in df.columns:
        df['Budget_INR'] = np.random.randint(80000, 300000, len(df))
    if 'Unit_Price_INR' not in df.columns:
        df['Unit_Price_INR'] = np.random.randint(2000, 8000, len(df))
    return df

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# ── SESSION STATE ────────────────────────────────────────────────────────────────
if 'df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        st.session_state.df = process_dataframe(pd.read_csv(CSV_FILE))
    else:
        st.error("Critical Error: orders.csv not found.")
        st.stop()

if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'rag_ready' not in st.session_state:
    st.session_state.rag_ready = False

df = st.session_state.df

# ── BUILD RAG INDEX (once) ───────────────────────────────────────────────────────
@st.cache_resource
def build_rag(df):
    deliveries = df[['ProductID', 'WarehouseID']].copy()
    if 'Shipping times' in df.columns:
        deliveries['DeliveryStatus'] = np.where(
            df['Shipping times'] > df['Shipping times'].mean(), 'Delayed', 'Delivered'
        )
        deliveries['DelayReason'] = deliveries['DeliveryStatus'].apply(
            lambda x: np.random.choice(['Traffic Issue', 'Supplier Delay', 'Low Stock']) if x == 'Delayed' else 'None'
        )
    else:
        deliveries['DeliveryStatus'] = 'Delivered'
        deliveries['DelayReason'] = 'None'

    docs = deliveries.apply(
        lambda r: f"Product {r['ProductID']} in {r['WarehouseID']} was {r['DeliveryStatus']} due to {r['DelayReason']}",
        axis=1
    ).tolist()

    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(docs).astype('float32')
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    return model, index, docs

model, faiss_index, rag_docs = build_rag(df)

# ── KPI METRICS WITH DELTA ───────────────────────────────────────────────────────
st.subheader("📊 Network KPIs")
m1, m2, m3, m4, m5 = st.columns(5)

total_budget   = df['Budget_INR'].sum()
inventory_val  = (df['StockLevel'] * df['Unit_Price_INR']).sum()
settled_count  = len(st.session_state.transaction_history)
low_stock      = int((df['StockLevel'] < 10).sum())

if 'Shipping times' in df.columns:
    delayed_count = int((df['Shipping times'] > df['Shipping times'].mean()).sum())
else:
    delayed_count = 0

m1.metric("Network Liquidity",      f"₹{total_budget:,}",      delta="Live")
m2.metric("Inventory Asset Value",  f"₹{inventory_val:,}",     delta="Live")
m3.metric("Settled Transactions",   settled_count,              delta=f"+{settled_count} today")
m4.metric("Low Stock Nodes",        low_stock,                  delta=f"{low_stock} critical", delta_color="inverse")
m5.metric("Delayed Shipments",      delayed_count,              delta=f"▲ {max(0, delayed_count-5)} vs avg", delta_color="inverse")

# ── PLOTLY CHARTS ────────────────────────────────────────────────────────────────
st.write("---")
st.subheader("📈 Visual Analytics")

tab1, tab2, tab3 = st.tabs(["Stock by Warehouse", "Delivery Status", "Budget Utilization"])

with tab1:
    wh_stock = df.groupby('WarehouseID')['StockLevel'].sum().reset_index()
    fig1 = px.bar(
        wh_stock, x='WarehouseID', y='StockLevel',
        color='StockLevel', color_continuous_scale='RdYlGn',
        title="Total Stock Level by Warehouse",
        labels={'StockLevel': 'Total Units', 'WarehouseID': 'Warehouse'}
    )
    fig1.update_layout(showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    if 'Shipping times' in df.columns:
        df['DeliveryStatus'] = np.where(
            df['Shipping times'] > df['Shipping times'].mean(), 'Delayed', 'Delivered'
        )
        status_counts = df['DeliveryStatus'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig2 = px.pie(
            status_counts, names='Status', values='Count',
            color='Status',
            color_discrete_map={'Delivered': '#2ecc71', 'Delayed': '#e74c3c'},
            title="Delivery Status Distribution",
            hole=0.4
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Shipping times column not found.")

with tab3:
    cat_budget = df.groupby('Category').agg(
        Total_Budget=('Budget_INR', 'sum'),
        Inventory_Cost=('Unit_Price_INR', 'sum')
    ).reset_index()
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(name='Total Budget',     x=cat_budget['Category'], y=cat_budget['Total_Budget'],     marker_color='#3498db'))
    fig3.add_trace(go.Bar(name='Inventory Cost',   x=cat_budget['Category'], y=cat_budget['Inventory_Cost'],   marker_color='#e67e22'))
    fig3.update_layout(barmode='group', title="Budget vs Inventory Cost by Category")
    st.plotly_chart(fig3, use_container_width=True)

# ── AI CHATBOT PANEL ─────────────────────────────────────────────────────────────
st.write("---")
st.subheader("🤖 AI Supply Chain Analyst")
st.caption("Ask anything: 'Which warehouse is at risk?', 'Why are products delayed?', 'Suggest replenishment strategy'")

api_key = os.getenv("GROQ_API_KEY")

chat_col, history_col = st.columns([3, 2])

with chat_col:
    user_query = st.text_input("Your question:", placeholder="e.g. Which warehouse has the most delays?", key="chat_input")

    if st.button("Ask AI", type="primary") and user_query:
        if not api_key:
            st.error("GROQ_API_KEY not set. Add it to your environment variables.")
        else:
            with st.spinner("Thinking..."):
                # RAG retrieval
                q_emb = model.encode([user_query]).astype('float32')
                D, I = faiss_index.search(q_emb, k=5)
                context = "\n".join([rag_docs[i] for i in I[0]])

                # Live data summary for context
                data_summary = f"""
Current warehouse summary:
{df.groupby('WarehouseID')[['StockLevel','Budget_INR']].sum().to_string()}

Low stock products (StockLevel < 10):
{df[df['StockLevel'] < 10][['ProductID','WarehouseID','StockLevel','Budget_INR']].to_string()}
"""
                prompt = f"""You are an expert supply chain analyst for an Indian FMCG company.

Historical context from records:
{context}

Live operational data:
{data_summary}

User question: {user_query}

Give a concise, actionable answer in 3-5 bullet points. Be specific with warehouse names and numbers."""

                try:
                    client = Groq(api_key=api_key)
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": "You are a supply chain expert analyst. Be concise and data-driven."},
                            {"role": "user",   "content": prompt}
                        ],
                        max_tokens=500
                    )
                    answer = response.choices[0].message.content
                    st.session_state.chat_history.append({"q": user_query, "a": answer})
                except Exception as e:
                    st.error(f"Groq Error: {e}")

    # Show latest answer prominently
    if st.session_state.chat_history:
        latest = st.session_state.chat_history[-1]
        st.success(f"**Q:** {latest['q']}")
        st.markdown(latest['a'])

with history_col:
    if st.session_state.chat_history:
        st.markdown("**Chat History**")
        for i, item in enumerate(reversed(st.session_state.chat_history[-5:])):
            with st.expander(f"Q{len(st.session_state.chat_history)-i}: {item['q'][:40]}..."):
                st.write(item['a'])
    else:
        st.info("No chat history yet. Ask a question!")

# ── SEARCH & TRANSACTION ─────────────────────────────────────────────────────────
st.write("---")
st.subheader("🔍 Strategic Sourcing & Landed Cost Optimization")

target_sku = st.text_input("Search SKU to optimize (e.g., SKU1):").upper()

if target_sku:
    sku_rows = df[df['ProductID'] == target_sku]
    if not sku_rows.empty:
        target_row = sku_rows.loc[sku_rows['StockLevel'].idxmin()]
        st.info(f"**Target Node:** {target_row['WarehouseID']} | **Budget:** ₹{target_row['Budget_INR']:,} | **Stock:** {target_row['StockLevel']}")

        suppliers = df[(df['WarehouseID'] != target_row['WarehouseID']) & (df['StockLevel'] > 5)].copy()
        suppliers['Distance'] = suppliers['WarehouseID'].apply(lambda x: get_distance(target_row['WarehouseID'], x))
        suppliers = suppliers.sort_values(by='Distance').head(2)

        for idx, supplier in suppliers.iterrows():
            with st.container(border=True):
                c_info, c_input, c_exec = st.columns([2, 1, 1])

                unit_price   = target_row['Unit_Price_INR']
                dist         = supplier['Distance']
                ship_rate    = 0.75
                max_affordable = int(target_row['Budget_INR'] // (unit_price + (dist * ship_rate))) if (unit_price + dist * ship_rate) > 0 else 0

                with c_info:
                    st.write(f"### Source: {supplier['WarehouseID']}")
                    st.write(f"**Surplus Available:** {supplier['StockLevel']} units")
                    st.write(f"**Distance:** {dist} km ({'Local' if dist < 300 else 'Interstate'})")
                    st.write(f"**Max Affordable:** {max_affordable} units (Inc. Freight)")

                with c_input:
                    move_qty       = st.number_input(f"Qty from {supplier['WarehouseID']}:",
                                                     min_value=0, max_value=int(supplier['StockLevel']),
                                                     value=min(max_affordable, 10) if max_affordable > 0 else 0,
                                                     key=f"qty_{idx}")
                    prod_cost      = move_qty * unit_price
                    trans_cost     = int(move_qty * dist * ship_rate)
                    total_landed   = prod_cost + trans_cost

                    st.write(f"Product:  ₹{prod_cost:,}")
                    st.write(f"Freight:  ₹{trans_cost:,}")
                    st.write(f"**Total Landed:** ₹{total_landed:,}")

                with c_exec:
                    if total_landed > target_row['Budget_INR']:
                        st.error("Insolvent")
                    elif move_qty == 0:
                        st.warning("Adjust Quantity")
                    else:
                        if st.button("Confirm & Settle", key=f"btn_{idx}"):
                            st.session_state.df.loc[target_row.name, 'StockLevel']  += move_qty
                            st.session_state.df.loc[target_row.name, 'Budget_INR'] -= total_landed
                            st.session_state.df.loc[supplier.name,   'StockLevel'] -= move_qty
                            st.session_state.df.loc[supplier.name,   'Budget_INR'] += prod_cost

                            st.session_state.transaction_history.append({
                                "sku":   target_sku,
                                "from":  supplier['WarehouseID'],
                                "to":    target_row['WarehouseID'],
                                "qty":   move_qty,
                                "val":   total_landed,
                                "dist":  dist,
                                "t_bal": f"₹{target_row['Budget_INR']:,} ➔ ₹{target_row['Budget_INR'] - total_landed:,}",
                                "g_bal": f"₹{supplier['Budget_INR']:,} ➔ ₹{supplier['Budget_INR'] + prod_cost:,}"
                            })
                            save_data(st.session_state.df)
                            st.balloons()
                            st.rerun()
    else:
        st.warning(f"SKU '{target_sku}' not found.")

# ── SEGMENTED LEDGERS ────────────────────────────────────────────────────────────
st.write("---")
st.subheader("📋 Segmented Operational Ledgers")

for cat in sorted(df['Category'].unique()):
    st.markdown(f"### 🏷️ {cat}")
    cat_df = df[df['Category'] == cat].sort_values(by='ProductID')

    critical_risk = cat_df[(cat_df['StockLevel'] < 10) & (cat_df['Budget_INR'] < 40000)]
    stock_risk    = cat_df[(cat_df['StockLevel'] < 10) & (cat_df['Budget_INR'] >= 40000)]

    if not critical_risk.empty:
        st.error(f"🔴 CRITICAL SOLVENCY RISK: {len(critical_risk)} node(s) cannot afford replenishment.")
        st.caption("📋 Action: Emergency Budget Request Required.")
    elif not stock_risk.empty:
        st.warning(f"🟡 REPLENISHMENT ALERT: {len(stock_risk)} node(s) low on stock.")

    st.dataframe(
        cat_df.style
              .highlight_min(subset=['StockLevel'], color='#ff4b4b')
              .highlight_max(subset=['Budget_INR'], color='#90ee90'),
        use_container_width=True
    )

# ── TRANSACTION AUDIT + EXPORT ───────────────────────────────────────────────────
if st.session_state.transaction_history:
    st.write("---")
    st.subheader("📑 Transaction Audit Trail")

    tx_df = pd.DataFrame(st.session_state.transaction_history)

    # CSV Export
    csv_bytes = tx_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Export Audit Trail (CSV)",
        data=csv_bytes,
        file_name="supply_chain_audit.csv",
        mime="text/csv"
    )

    # PDF Export
    def generate_pdf(tx_df):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Supply Chain Transaction Audit Report", ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Total Transactions: {len(tx_df)}", ln=True)
        pdf.ln(4)

        cols   = list(tx_df.columns)
        widths = [25, 25, 25, 15, 25, 15, 30, 30][:len(cols)]

        pdf.set_font("Helvetica", "B", 9)
        for col, w in zip(cols, widths):
            pdf.cell(w, 8, str(col)[:12], border=1)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for _, row in tx_df.iterrows():
            for col, w in zip(cols, widths):
                pdf.cell(w, 7, str(row[col])[:14], border=1)
            pdf.ln()

        return bytes(pdf.output())

    pdf_bytes = generate_pdf(tx_df)
    st.download_button(
        label="⬇️ Export Audit Report (PDF)",
        data=pdf_bytes,
        file_name="supply_chain_audit.pdf",
        mime="application/pdf"
    )

    # Display audit
    for tx in reversed(st.session_state.transaction_history):
        with st.expander(f"✅ {tx['qty']} units | {tx['from']} ➔ {tx['to']} ({tx['dist']} km)", expanded=False):
            ca, cb, cc = st.columns(3)
            ca.write(f"**Total Cost:** ₹{tx['val']:,}")
            cb.write(f"**Taker Balance:** {tx['t_bal']}")
            cc.write(f"**Giver Balance:** {tx['g_bal']}")
