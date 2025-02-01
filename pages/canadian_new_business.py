import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from pathlib import Path
import os

# --- Utility Functions ---

def get_data_path(filename):
    """
    Returns the absolute path to a data file.
      - If the filename starts with "historical_", it is assumed to be in the 'market-data' folder.
      - Otherwise, the file is assumed to be in a 'data' folder at the repository root.
    """
    BASE_DIR = Path(__file__).resolve().parent.parent
    if filename.startswith("historical_"):
        return str(BASE_DIR / "market-data" / filename)
    else:
        return str(BASE_DIR / "data" / filename)

def get_rates_csv(province, commodity):
    """
    Returns the appropriate historical rates CSV filename based on province and commodity.
    """
    if province == "Alberta" and commodity == "gas":
        return "historical_data_AB_gas.csv"
    elif province == "Alberta" and commodity == "electricity":
        return "historical_data_AB_ele.csv"
    elif province == "Ontario" and commodity == "gas":
        return "historical_data_ON_gas.csv"
    elif province == "Quebec" and commodity == "gas":
        return "historical_data_QC_gas.csv"
    else:
        st.error(f"No rate file rule for province={province}, commodity={commodity}")
        st.stop()

def cost_in_cad(usage, rate, province, commodity):
    """
    A simple cost calculation:
      - For Alberta gas: cost = usage * rate
      - For Alberta electricity: cost = usage * (rate / 100)
      - For Ontario and Quebec gas: cost = usage * (rate / 100)
    """
    if province == "Alberta" and commodity == "gas":
        return usage * rate
    elif province == "Alberta" and commodity == "electricity":
        return usage * (rate / 100.0)
    elif (province == "Ontario" or province == "Quebec") and commodity == "gas":
        return usage * (rate / 100.0)
    else:
        st.error(f"No cost calculation rule for {province}, {commodity}")
        st.stop()

# --- Main Application Function ---

def main():
    st.title("Market Performance Simulator (CAD) - New Business")
    st.write("This tool simulates market performance for new business scenarios based on manually supplied consumer data.")
    
    # If clear_results flag is set, do not show simulation results.
    if "clear_results" not in st.session_state:
        st.session_state.clear_results = False

    with st.form("new_business_form"):
        # --- Section 1: Market Information ---
        st.subheader("Market Information")
        col1, col2 = st.columns(2)
        selected_province = col1.selectbox("Select Province:", ["Alberta", "Ontario", "Quebec"], key="selected_province")
        if selected_province == "Alberta":
            commodity_options = ["gas", "electricity"]
        else:
            # For Ontario and Quebec, only gas is supported.
            commodity_options = ["gas"]
        selected_commodity = col2.selectbox("Select Commodity:", commodity_options, key="selected_commodity")
        
        # --- Section 2: Simulation Details ---
        st.subheader("Simulation Details")
        col1, col2 = st.columns(2)
        simulation_start = col1.date_input("Simulation Start Date", value=datetime(2023, 1, 1), key="simulation_start")
        simulation_end = col2.date_input("Simulation End Date", value=datetime(2023, 12, 31), min_value=simulation_start, key="simulation_end")
        admin_fee = st.number_input("Admin Fee", min_value=0.0, step=0.1, format="%.2f", key="admin_fee")
        
        # --- Section 3: Monthly Consumption ---
        st.subheader("Monthly Consumption")
        month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        consumption = {}
        for m in month_names:
            consumption[m] = st.number_input(f"{m} Consumption", min_value=0, step=1, format="%d", key=f"consumption_{m}")
        
        # --- Section 4: Hedge Options (Optional) ---
        st.subheader("Hedge Options (Optional)")
        use_hedge = st.checkbox("Include Volumetric Hedge?", key="use_hedge")
        hedge_portion_percent = 0.0
        hedge_start_date = None
        hedge_term_months = 0
        hedge_fixed_rate = 0.0
        if use_hedge:
            hedge_portion_percent = st.number_input("Hedged Portion (%)", min_value=0.0, max_value=100.0, step=1.0, value=30.0, key="hedge_portion_percent")
            hedge_start_date = st.date_input("Hedge Start Date", value=simulation_start, min_value=simulation_start, max_value=simulation_end, key="hedge_start_date")
            hedge_term_months = st.number_input("Hedge Term (months)", min_value=0, value=6, key="hedge_term_months")
            hedge_fixed_rate = st.number_input("Hedge Fixed Rate (All-Inclusive)", min_value=0.0, step=0.1, format="%.2f", key="hedge_fixed_rate")
        
        # --- Section 5: Additional Options ---
        st.subheader("Additional Options")
        show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True, key="show_monthly_chart")
        show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True, key="show_monthly_table")
        if selected_commodity == "gas":
            equalize_consumption_checkbox = st.checkbox("Bundle-T Billing (Gas Only)", value=False, key="equalize_consumption")
        else:
            equalize_consumption_checkbox = False
        
        submitted = st.form_submit_button("Run Simulation")
    
    # When form is (re)submitted, clear_results flag is reset.
    if submitted:
        st.session_state.clear_results = False

    if submitted and not st.session_state.clear_results:
        # Load historical rates.
        rates_csv = get_rates_csv(selected_province, selected_commodity)
        try:
            df_rates = pd.read_csv(get_data_path(rates_csv), parse_dates=["date"])
        except FileNotFoundError:
            st.error(f"Could not find rates file '{rates_csv}'. Please check your files.")
            st.stop()
        
        start_ts = pd.to_datetime(simulation_start)
        end_ts = pd.to_datetime(simulation_end)
        mask = (df_rates["date"] >= start_ts) & (df_rates["date"] <= end_ts)
        df_filtered = df_rates.loc[mask].copy()
        if df_filtered.empty:
            st.error("No historical rate data found in the selected date range.")
            st.stop()
        
        # Set utility rate column based on province.
        if selected_province == "Alberta":
            df_filtered["utility_selected"] = df_filtered["regulated_rate"]
        elif selected_province == "Quebec":
            df_filtered["utility_selected"] = df_filtered["utility_rate"]
        elif selected_province == "Ontario":
            df_filtered["utility_selected"] = df_filtered["local_utility_rate_egd"]
        
        # Group the historical data by month.
        df_filtered["year_month"] = df_filtered["date"].dt.to_period("M")
        monthly_rates = df_filtered.groupby("year_month", as_index=False).agg({
            "wholesale_rate": "mean",
            "utility_selected": "mean"
        })
        monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
        monthly_rates.sort_values("year_month", inplace=True)
        monthly_rates.reset_index(drop=True, inplace=True)
        
        st.subheader("Historical Data Preview")
        st.dataframe(df_filtered.head())
        
        # Convert manually entered consumption into a dictionary keyed by month number.
        consumption_by_num = {}
        for i, m in enumerate(month_names, start=1):
            consumption_by_num[i] = consumption[m]
        
        # Compute uniform consumption if Bundle-T Billing is enabled.
        if selected_commodity == "gas" and equalize_consumption_checkbox:
            equal_consumption = sum(consumption_by_num.values()) / 12
        
        # Calculate monthly costs.
        monthly_cost_utility = []
        monthly_cost_client = []
        for _, row in monthly_rates.iterrows():
            month_dt = row["year_month"]
            w_rate = row["wholesale_rate"]
            u_rate = row["utility_selected"]
            mnum = pd.Timestamp(month_dt).month
            actual_usage = consumption_by_num[mnum]
            # Utility cost always uses the actual consumption.
            util_cost = cost_in_cad(actual_usage, u_rate, selected_province, selected_commodity)
            # For client cost, use the equalized consumption if Bundle-T Billing is enabled.
            if selected_commodity == "gas" and equalize_consumption_checkbox:
                usage_val_client = equal_consumption
            else:
                usage_val_client = actual_usage
            # Apply hedge adjustments if required.
            if use_hedge and hedge_start_date:
                hedge_start_ts = pd.to_datetime(hedge_start_date)
                hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
                if hedge_start_ts <= month_dt < hedge_end_ts:
                    hedged_vol = usage_val_client * (hedge_portion_percent / 100.0)
                    floating_vol = usage_val_client - hedged_vol
                    cost_hedged = cost_in_cad(hedged_vol, hedge_fixed_rate, selected_province, selected_commodity)
                    cost_floating = cost_in_cad(floating_vol, w_rate + admin_fee, selected_province, selected_commodity)
                    client_cost = cost_hedged + cost_floating
                else:
                    client_cost = cost_in_cad(usage_val_client, w_rate + admin_fee, selected_province, selected_commodity)
            else:
                client_cost = cost_in_cad(usage_val_client, w_rate + admin_fee, selected_province, selected_commodity)
            monthly_cost_utility.append(util_cost)
            monthly_cost_client.append(client_cost)
        
        total_utility = sum(monthly_cost_utility)
        total_client = sum(monthly_cost_client)
        
        st.header("Cost Comparison Report (CAD)")
        colA, colB = st.columns(2)
        colA.metric("Utility Cost (CAD)", f"${total_utility:,.2f}")
        colB.metric("Client Cost (CAD)", f"${total_client:,.2f}")
        diff = total_utility - total_client
        st.write(f"**Difference (Utility - Client)**: ${diff:,.2f}")
        if diff > 0:
            st.success(f"You would have saved ${diff:,.2f} by using the Client Cost.")
        elif diff < 0:
            st.error(f"You would have spent ${-diff:,.2f} more by using the Client Cost.")
        else:
            st.info("No difference between Utility and Client Cost.")
        
        # --- Monthly Breakdown Table and Chart ---
        monthly_display = []
        for i, row_m in enumerate(monthly_rates.itertuples()):
            date_label = row_m.year_month
            month_str = pd.Timestamp(date_label).strftime("%b %Y")
            cost_util = monthly_cost_utility[i]
            cost_client = monthly_cost_client[i]
            diff_month = cost_util - cost_client
            monthly_data = {
                "Month": month_str,
                "Utility Cost (CAD)": cost_util,
                "Client Cost (CAD)": cost_client,
                "Diff (Utility - Client)": diff_month
            }
            monthly_display.append(monthly_data)
        monthly_df = pd.DataFrame(monthly_display)
        
        if show_monthly_chart and not monthly_df.empty:
            st.write("### Monthly Bar Chart of Costs (CAD)")
            chart_data = monthly_df.melt(
                id_vars="Month",
                value_vars=["Utility Cost (CAD)", "Client Cost (CAD)"],
                var_name="Scenario",
                value_name="Cost (CAD)"
            )
            chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X("Month:N", sort=None, title="Month"),
                y=alt.Y("Cost (CAD):Q", title="Cost in CAD"),
                color=alt.Color("Scenario:N", legend=alt.Legend(title="Scenario")),
                xOffset="Scenario:N"
            ).properties(width=600, height=400)
            st.altair_chart(chart, use_container_width=True)
        
        if show_monthly_table and not monthly_df.empty:
            st.write("### Monthly Costs & Differences Table (CAD)")
            format_dict = {
                "Utility Cost (CAD)": "{:,.2f}",
                "Client Cost (CAD)": "{:,.2f}",
                "Diff (Utility - Client)": "{:,.2f}"
            }
            existing_cols = list(monthly_df.columns)
            formatable_cols = {col: format_dict[col] for col in existing_cols if col in format_dict}
            st.dataframe(monthly_df.style.format(formatable_cols))
        
        # Add a button to clear the results and return to the pre-submission state.
        if st.button("Clear Results"):
            st.session_state.clear_results = True
            st.experimental_rerun()

if __name__ == "__main__":
    main()
