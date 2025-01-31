import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

# -------------------------------
# Main Application Function
# -------------------------------
def main():
    st.image("assets/capitalmarketslogo.png", width=400)
    st.title("Quebec Natural Gas Market Simulator (CAD)")
    
    st.write("""
    This tool compares:
    1. **Utility Cost** (Regulated Rate)
    2. **Client Cost** (Wholesale + Admin Fee)
    with an optional **Volumetric Hedge** (partial fixed rate).
    
    **Features for Quebec Natural Gas Clients:**
    - **Volumes:** m³
    - **Rates:** cents/m³
    - **Final Values:** dollars (CAD)
    - **Historical Data:** `historical_data_QC_gas.csv`
    - **Volume Redistribution:** Equally distribute client volumes across all months for client costs.
    
    **Note:** Hedge pricing is **inclusive** of fees, meaning **no separate admin fee** is added to the hedge price.
    """)
    
    # -------------------------------
    # 1. Load Historical Rate Data
    # -------------------------------
    st.header("Historical Rate Data")
    csv_path = "/workspaces/blank-app/market-data/historical_data_AB_ele.csv"
    try:
        df = pd.read_csv(csv_path, parse_dates=["date"])
    except FileNotFoundError:
        st.error(f"Could not find '{csv_path}'. Please ensure the file exists at that path.")
        st.stop()

    required_columns = {"date", "utility_rate", "wholesale_rate"}
    if not required_columns.issubset(df.columns):
        st.error(f"CSV is missing required columns. Expected columns: {required_columns}")
        st.stop()

    # Determine min/max date from CSV
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    st.subheader("Reference Data (Preview)")
    st.write("Below is a quick preview of the loaded historical data:")
    st.dataframe(df.head())

    # -------------------------------
    # 2. Date Range Selection and Admin Fee
    # -------------------------------
    st.header("Date Range and Administrative Fee")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date_input = st.date_input(
            "Start Date",
            value=min_date,
            min_value=min_date,
            max_value=max_date
        )
    with col2:
        end_date_input = st.date_input(
            "End Date",
            value=max_date,
            min_value=start_date_input,
            max_value=max_date
        )
    with col3:
        admin_fee = st.number_input(
            "Admin Fee (cents/m³)",
            min_value=0.0,
            step=0.1,
            format="%.2f",
            value=0.0
        )
    
    # -------------------------------
    # 3. Monthly Consumption Input
    # -------------------------------
    st.header("Monthly Consumption Patterns (m³)")
    MONTH_NAMES = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    consumption = {}
    for i, name in enumerate(MONTH_NAMES, start=1):
        consumption[i] = st.number_input(
            f"{name}",
            min_value=0.0,
            step=10.0,
            format="%.2f",
            value=0.0
        )
    
    # -------------------------------
    # 4. Volumetric Hedge Configuration
    # -------------------------------
    st.header("Volumetric Hedge")
    st.write("""
    Define a partial fixed-rate hedge. Hedge pricing here is **inclusive** of all fees, meaning 
    **no separate admin fee** will be added on top of the hedge price.
    """)
    use_hedge = st.checkbox("Include Volumetric Hedge?", value=False)
    
    hedge_portion_percent = 0.0
    hedge_start_date_input = None
    hedge_term_months = 0
    hedge_fixed_rate = 0.0
    
    if use_hedge:
        hedge_portion_percent = st.number_input(
            "Hedged portion of monthly volume (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            value=30.0
        )
        hedge_start_date_input = st.date_input(
            "Hedge Start Date",
            value=start_date_input,
            min_value=start_date_input,
            max_value=end_date_input
        )
        hedge_term_months = st.number_input(
            "Hedge Term (months)",
            min_value=1,
            step=1,
            value=6
        )
        hedge_fixed_rate = st.number_input(
            "Hedge Fixed Rate (cents/m³)",
            min_value=0.0,
            step=0.1,
            format="%.2f",
            value=0.0
        )
    
    # -------------------------------
    # 5. Volume Redistribution for Quebec Gas Clients
    # -------------------------------
    st.header("Volume Redistribution for Client Costs")
    st.write("""
    **Note:** This feature redistributes client volumes equally across all months for **Client Costs** only.
    Utility Costs remain based on original monthly consumption.
    """)
    redistribute_option = st.checkbox(
        "Equally redistribute client volumes across all months for Client Costs?",
        value=True  # Checked by default
    )
    
    # -------------------------------
    # 6. Additional Options
    # -------------------------------
    st.header("Additional Options")
    show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
    show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)
    
    # -------------------------------
    # 7. Submit Button
    # -------------------------------
    submitted = st.button("Submit", type="primary")
    if not submitted:
        st.stop()
    
    # -------------------------------
    # 8. Post-Submit Logic
    # -------------------------------
    # Convert date inputs to Timestamps
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)
    
    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_start_ts = None
        hedge_end_ts = None
    
    # -------------------------------
    # 9. Load Historical Rate Data
    # -------------------------------
    try:
        df_rates = pd.read_csv(csv_path, parse_dates=["date"])
    except FileNotFoundError:
        st.error(f"Could not find historical rates file '{csv_path}'. Please ensure it exists.")
        st.stop()
    
    # -------------------------------
    # 10. Validate Historical Rate Columns
    # -------------------------------
    if not required_cols.issubset(df_rates.columns):
        st.error(f"Historical rates file '{csv_path}' must contain columns: {required_cols}")
        st.stop()
    
    # -------------------------------
    # 11. Display Historical Data Preview
    # -------------------------------
    st.subheader("Reference Data (Filtered)")
    st.write("Averaged monthly data within the selected date range:")
    
    # -------------------------------
    # 12. Filter Rates by Date Range
    # -------------------------------
    mask = (df_rates["date"] >= start_ts) & (df_rates["date"] <= end_ts)
    df_filtered_rates = df_rates.loc[mask].copy()
    if df_filtered_rates.empty:
        st.warning("No rate data found for the selected date range. Please adjust your dates or check your CSV.")
        st.stop()
    
    # -------------------------------
    # 13. Aggregate Monthly Rates
    # -------------------------------
    df_filtered_rates["year_month"] = df_filtered_rates["date"].dt.to_period("M")
    monthly_rates = (
        df_filtered_rates
        .groupby("year_month", as_index=False)
        .agg({
            "utility_rate": "mean",     # cents/m³
            "wholesale_rate": "mean"    # cents/m³
        })
    )
    monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
    monthly_rates.sort_values("year_month", inplace=True)
    monthly_rates.reset_index(drop=True, inplace=True)
    
    st.dataframe(monthly_rates.head())
    
    # -------------------------------
    # 14. Calculate Monthly Costs
    # -------------------------------
    monthly_cost_utility = []
    monthly_cost_client = []
    
    for _, row in monthly_rates.iterrows():
        month_datetime = pd.Timestamp(row["year_month"])
        utility_rate = row["utility_rate"]      # cents/m³
        wholesale_rate = row["wholesale_rate"]  # cents/m³
        
        mnum = month_datetime.month
        usage_val = consumption[mnum]  # m³
        
        # Utility Cost (Regulated Rate)
        cost_utility = (usage_val * utility_rate) / 100.0  # dollars
        
        # Client Cost (Wholesale + Admin Fee, with optional Hedge)
        if use_hedge and hedge_start_ts and (hedge_start_ts <= month_datetime < hedge_end_ts):
            # Hedged Portion
            hedged_volume = usage_val * (hedge_portion_percent / 100.0)
            floating_volume = usage_val - hedged_volume
            
            # Hedge Cost (inclusive of fees)
            cost_hedged = (hedged_volume * hedge_fixed_rate) / 100.0  # dollars
            
            # Floating Cost (wholesale_rate + admin_fee)
            cost_floating = (floating_volume * (wholesale_rate + admin_fee)) / 100.0  # dollars
            
            cost_client = cost_hedged + cost_floating
        else:
            # Fully Unhedged
            cost_client = (usage_val * (wholesale_rate + admin_fee)) / 100.0  # dollars
        
        monthly_cost_utility.append(cost_utility)
        monthly_cost_client.append(cost_client)
    
    # -------------------------------
    # 15. Volume Redistribution for Client Costs
    # -------------------------------
    if redistribute_option:
        st.write("**Volume Redistribution Enabled:** Client volumes are equally distributed across all months for Client Costs.")
        
        # Total consumption
        total_consumption = sum(consumption.values())
        if total_consumption == 0:
            st.warning("Total consumption is zero. Redistribution cannot be performed.")
            redistribute_enabled = False
        else:
            equal_monthly_consumption = total_consumption / 12.0  # m³ per month
            
            # Create a new dataframe with equal consumption
            redistributed_df = monthly_rates.copy()
            redistributed_df["redistributed_consumption"] = equal_monthly_consumption
            
            # Calculate redistributed client costs
            redistributed_cost_client = []
            for _, row in redistributed_df.iterrows():
                usage_val = row["redistributed_consumption"]  # m³
                wholesale_rate = row["wholesale_rate"]      # cents/m³
                utility_rate = row["utility_rate"]          # cents/m³
                
                # Check if hedge applies
                if use_hedge and hedge_start_ts and (hedge_start_ts <= row["year_month"] < hedge_end_ts):
                    # Hedged Portion
                    hedged_volume = usage_val * (hedge_portion_percent / 100.0)
                    floating_volume = usage_val - hedged_volume
                    
                    # Hedge Cost (inclusive of fees)
                    cost_hedged = (hedged_volume * hedge_fixed_rate) / 100.0  # dollars
                    
                    # Floating Cost (wholesale_rate + admin_fee)
                    cost_floating = (floating_volume * (wholesale_rate + admin_fee)) / 100.0  # dollars
                    
                    client_cost = cost_hedged + cost_floating
                else:
                    # Fully Unhedged
                    client_cost = (usage_val * (wholesale_rate + admin_fee)) / 100.0  # dollars
                
                redistributed_cost_client.append(client_cost)
            
            # Add to redistributed dataframe
            redistributed_df["Client Cost (CAD)"] = redistributed_cost_client
    else:
        redistributed_df = None
    
    # -------------------------------
    # 16. Summarize Costs
    # -------------------------------
    total_utility = sum(monthly_cost_utility)
    total_client = sum(monthly_cost_client)
    
    # -------------------------------
    # 17. Reporting
    # -------------------------------
    st.header("Cost Comparison Report (CAD)")
    colA, colB = st.columns(2)
    colA.metric("Utility Cost (CAD)", f"${total_utility:,.2f}")
    colB.metric("Client Cost (CAD)", f"${total_client:,.2f}")
    
    diff_val = total_utility - total_client
    st.write("### Difference in Total Cost (CAD)")
    st.write(f"**Utility - Client**: ${diff_val:,.2f}")
    
    if diff_val > 0:
        st.success(f"You would have saved ${diff_val:,.2f} by using the Client Cost (vs. Utility).")
    elif diff_val < 0:
        st.error(f"You would have spent ${-diff_val:,.2f} more by using the Client Cost (vs. Utility).")
    else:
        st.info("No difference between Utility and Client Cost.")
    
    # -------------------------------
    # 18. Volume Redistribution Reporting
    # -------------------------------
    if redistribute_option and redistributed_df is not None:
        redistributed_total_client = sum(redistributed_df["Client Cost (CAD)"])
        
        st.header("Cost Comparison with Redistributed Client Volumes (CAD)")
        colA_r, colB_r = st.columns(2)
        colA_r.metric("Utility Cost (CAD)", f"${total_utility:,.2f}")
        colB_r.metric("Redistributed Client Cost (CAD)", f"${redistributed_total_client:,.2f}")
        
        diff_val_r = total_utility - redistributed_total_client
        st.write("### Difference in Total Cost (CAD) with Redistribution")
        st.write(f"**Utility - Redistributed Client**: ${diff_val_r:,.2f}")
        
        if diff_val_r > 0:
            st.success(f"You would have saved ${diff_val_r:,.2f} by redistributing client volumes.")
        elif diff_val_r < 0:
            st.error(f"You would have spent ${-diff_val_r:,.2f} more by redistributing client volumes.")
        else:
            st.info("No difference between Utility and Redistributed Client Cost.")
    
    # -------------------------------
    # 19. Optional Monthly Breakdown
    # -------------------------------
    monthly_display = []
    for idx, row in monthly_rates.iterrows():
        date_label = pd.Timestamp(row["year_month"])
        month_str = date_label.strftime("%b %Y")
        
        cost_util = monthly_cost_utility[idx]
        cost_client = monthly_cost_client[idx]
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
        ).properties(
            width=600,
            height=400
        )
        st.altair_chart(chart, use_container_width=True)
    
    if show_monthly_table and not monthly_df.empty:
        st.write("### Monthly Costs & Differences Table (CAD)")
        format_dict = {
            "Utility Cost (CAD)": "{:,.2f}",
            "Client Cost (CAD)": "{:,.2f}",
            "Diff (Utility - Client)": "{:,.2f}"
        }
        st.dataframe(monthly_df.style.format(format_dict))
    
    # Display Redistribution Monthly Breakdown if enabled
    if redistribute_option and redistributed_df is not None:
        redistributed_display = []
        for idx, row in redistributed_df.iterrows():
            date_label = pd.Timestamp(row["year_month"])
            month_str = date_label.strftime("%b %Y")
            
            cost_util = monthly_cost_utility[idx]
            cost_client_r = row["Client Cost (CAD)"]
            diff_val_r = cost_util - cost_client_r
            
            monthly_data_r = {
                "Month": month_str,
                "Utility Cost (CAD)": cost_util,
                "Redistributed Client Cost (CAD)": cost_client_r,
                "Diff (Utility - Redistributed Client)": diff_val_r
            }
            redistributed_display.append(monthly_data_r)
        
        redistributed_monthly_df = pd.DataFrame(redistributed_display)
        
        if show_monthly_chart and not redistributed_monthly_df.empty:
            st.write("### Monthly Bar Chart of Costs with Redistributed Client Volumes (CAD)")
            chart_data_r = redistributed_monthly_df.melt(
                id_vars="Month",
                value_vars=["Utility Cost (CAD)", "Redistributed Client Cost (CAD)"],
                var_name="Scenario",
                value_name="Cost (CAD)"
            )
            chart_r = alt.Chart(chart_data_r).mark_bar().encode(
                x=alt.X("Month:N", sort=None, title="Month"),
                y=alt.Y("Cost (CAD):Q", title="Cost in CAD"),
                color=alt.Color("Scenario:N", legend=alt.Legend(title="Scenario")),
                xOffset="Scenario:N"
            ).properties(
                width=600,
                height=400
            )
            st.altair_chart(chart_r, use_container_width=True)
        
        if show_monthly_table and not redistributed_monthly_df.empty:
            st.write("### Monthly Costs & Differences Table with Redistributed Client Volumes (CAD)")
            format_dict_r = {
                "Utility Cost (CAD)": "{:,.2f}",
                "Redistributed Client Cost (CAD)": "{:,.2f}",
                "Diff (Utility - Redistributed Client)": "{:,.2f}"
            }
            st.dataframe(redistributed_monthly_df.style.format(format_dict_r))

# -------------------------------
# Helper Function for Cost Calculation
# -------------------------------
def cost_in_cad(usage_value, rate_value):
    """
    Calculate cost in CAD based on usage and rate.
    - All volumes: m³
    - All rates: cents/m³
    - Final cost: dollars (CAD)
    """
    return (usage_value * rate_value) / 100.0  # Convert cents to dollars

# -------------------------------
# Run the App
# -------------------------------
if __name__ == "__main__":
    main()
