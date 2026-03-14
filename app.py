import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- Industry Benchmarks ---
GENRE_BENCHMARKS = {
    "Pop / Current Hits": {"decay": 0.15, "multiple": 8.0, "desc": "High volatility, rapid initial decay."},
    "Hip-Hop / R&B": {"decay": 0.12, "multiple": 10.0, "desc": "Strong streaming, moderate decay."},
    "Classic Rock": {"decay": 0.04, "multiple": 14.0, "desc": "High stability, 'Evergreen' status."},
    "Jazz / Classical": {"decay": 0.02, "multiple": 12.0, "desc": "Very low decay, niche but loyal audience."},
    "Country": {"decay": 0.06, "multiple": 13.0, "desc": "High listener loyalty, steady tail."}
}

def calculate_valuation(initial, decay, discount, years, terminal_mult):
    data = []
    current_cf = float(initial)
    total_npv = 0
    for year in range(1, years + 1):
        current_cf *= (1 - decay)
        # Fix: Using mid-year discounting is technically more accurate for royalties,
        # but we'll stay with standard year-end for simplicity here.
        pv = current_cf / ((1 + discount) ** year)
        total_npv += pv
        data.append({"Period": year, "Cash Flow": round(current_cf, 2), "Present Value": round(pv, 2)})
    
    term_val = current_cf * terminal_mult
    term_pv = term_val / ((1 + discount) ** years)
    return total_npv + term_pv, pd.DataFrame(data), term_pv

# --- Streamlit UI ---
st.set_page_config(page_title="Music Valuator Master", layout="wide")
st.title("🎵 Music Catalog Master Valuation Suite")

# --- Debug Fix 1: Session State for Data Editor ---
# This ensures that when you move a slider, your historical data doesn't reset to defaults.
if 'hist_df' not in st.session_state:
    st.session_state.hist_df = pd.DataFrame({
        "Year": ["Y-5", "Y-4", "Y-3", "Y-2", "LTM"], 
        "Revenue": [60000.0, 58000.0, 55000.0, 52000.0, 50000.0]
    })

with st.sidebar:
    st.header("1. Historical & Genre")
    selected_genre = st.selectbox("Genre Template", list(GENRE_BENCHMARKS.keys()))
    
    # Use key="hist_editor" to track changes
    df_hist = st.data_editor(st.session_state.hist_df, num_rows="fixed", key="hist_editor")
    # Update session state with the edited values
    st.session_state.hist_df = df_hist
    
    ltm = df_hist["Revenue"].iloc[-1]

    st.header("2. Deal Parameters")
    # Debug Fix 2: Explicitly cast slider values to float to prevent MixedNumericTypesError
    decay = float(st.slider("Projected Decay (%)", 0.0, 40.0, float(GENRE_BENCHMARKS[selected_genre]['decay']*100))) / 100
    discount = float(st.slider("Discount Rate (%)", 1.0, 25.0, 12.0)) / 100
    exit_mult = float(st.number_input("Exit Multiple", value=float(GENRE_BENCHMARKS[selected_genre]['multiple']), step=0.1))

    st.header("3. Tax & Fees")
    tax_rate = float(st.slider("Tax Rate (%)", 0.0, 50.0, 20.0)) / 100
    broker_fee = float(st.slider("Broker/Legal (%)", 0.0, 10.0, 2.0)) / 100

# --- Computations ---
# We extend projection to 15 years to better calculate "Terminal Value" stability
total_val, df_proj, t_pv = calculate_valuation(ltm, decay, discount, 15, exit_mult)
net_proceeds = total_val * (1 - broker_fee) * (1 - tax_rate)

# --- Dashboard Layout ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("Gross Valuation", f"${total_val:,.0f}")
m2.metric("Net Take-Home", f"${net_proceeds:,.0f}")
m3.metric("Implied Multiple", f"{total_val/ltm:.1f}x")
# Debug Fix 3: Inverted delta color for decay (lower decay is "green"/good)
m4.metric("Genre Benchmark", f"{GENRE_BENCHMARKS[selected_genre]['decay']*100:.0f}%", 
          delta=f"{(decay - GENRE_BENCHMARKS[selected_genre]['decay'])*100:.1f}% vs Avg",
          delta_color="inverse")

st.divider()

# Charts
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Revenue Decay Projection (15 Years)")
    # Using 'Present Value' as the primary metric to show the impact of time
    fig_line = px.area(df_proj, x="Period", y=["Cash Flow", "Present Value"], 
                       barmode='overlay',
                       color_discrete_map={"Cash Flow": "#1DB954", "Present Value": "#191414"})
    st.plotly_chart(fig_line, use_container_width=True)

with col_right:
    st.subheader("Sensitivity Matrix")
    sens_matrix = []
    disc_steps = [discount - 0.02, discount, discount + 0.02]
    dec_steps = [decay - 0.02, decay, decay + 0.02]
    
    for d_rate in disc_steps:
        row = []
        for d_cay in dec_steps:
            v, _, _ = calculate_valuation(ltm, max(0, d_cay), max(0.01, d_rate), 15, exit_mult)
            row.append(f"${v/1000:.0f}k")
        sens_matrix.append(row)
    
    st.table(pd.DataFrame(sens_matrix, 
                          index=[f"Disc {i*100:.0f}%" for i in disc_steps], 
                          columns=[f"Decay {j*100:.0f}%" for j in dec_steps]))

st.subheader("Investment Recovery Analysis")
# Cumulative undiscounted cash flow
cumulative = df_proj["Cash Flow"].cumsum()
# Logic to find the first year where total_val is surpassed
payback_idx = (cumulative >= total_val).idxmax() if (cumulative >= total_val).any() else None
payback_year = df_proj.loc[payback_idx, "Period"] if payback_idx is not None else "15+ Years"

st.success(f"**Payback Period:** Recouping the ${total_val:,.0f} valuation would take approximately **{payback_year} years** of royalty earnings.")
