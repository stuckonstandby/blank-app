# Import necessary libraries
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import os

# Function to dynamically select the appropriate CSV based on province and commodity
def get_rates_csv(province, commodity):
    """
    Returns the CSV filename based on the province and commodity.
    """
    if province == "Alberta" and commodity == "gas":
        return "historical_data_AB_gas.csv"
    elif province == "Alberta" and commodity == "electricity":
        return "historical_data_AB_ele.csv"
    elif province == "Ontario" and commodity == "gas":
        return "historical_data_ON_gas.csv"
    elif province == "Ontario" and commodity == "electricity":
        return "historical_data_ON_ele.csv"
    else:
        st.error(f"No rate file rule for province={province}, commodity={commodity}")
        st.stop()

def main():
    st.title("Canadian Market Simulator (CAD) - Manual Input")

    st.write("""
    This tool compares:
    1. **Utility Cost** (Regulated Rate)
    2. **Client Cost** (Wholesale + Admin Fee)
    with an optional **Volumetric Hedge** (partial fixed rate).
    
    **Monthly consumption (GJ)** is entered manually below.
    """)

    # 1. Load Historical Rate Data (so we can limit date range)
    # Use relative path to ensure compatibility across environments
    # Assuming this script is in 'pages/' directory and data is in 'data/' directory
    script_dir = os.path.dirname(__file__)
    data_dir = os.path.join(script_dir, '..', 'data')
    
    # 2. User Inputs for Province and Commodity to select CSV
    st.header("Select Province and Commodity")
    province = st.selectbox("Select Province:", ["Alberta", "Ontario"])
    commodity = st.selectbox("Select Commodity:", ["gas", "electricity"])
    
    rates_csv = get_rates_csv(province, commodity)
    csv_path = os.path.join(data_dir, rates_csv)
    
    # Verify that the CSV file exists
    if not os.path.exists(csv_path):
        st.error(f"Could not find '{rates_csv}' in the data directory. Please ensure the file exists.")
        st.stop()
    
    try:
        df = pd.read_csv(csv_path, parse_dates=["date"])
    except Exception as e:
        st.error(f"Error reading the CSV file: {e}")
        st.stop()

    # Check for required columns
    if province == "Alberta" and commodity == "gas":
        required_columns = {"date", "regulated_rate", "wholesale_rate"}
    elif province == "Alberta" and commodity == "electricity":
        required_columns = {"date", "regulated_rate", "wholesale_rate"}
    elif province == "Ontario" and commodity == "gas":
        required_columns = {"date", "wholesale_rate", "local_utility_rate_egd", "local_utility_rate_usouth"}
    elif province == "Ontario" and commodity == "electricity":
        required_columns = {"date", "wholesale_rate", "local_utility_rate_egd", "local_utility_rate_usouth"}
    else:
        st.error(f"Unexpected combination of province and commodity: {province}, {commodity}")
        st.stop()

    if not required_columns.issubset(df.columns):
        st.error(f"CSV '{rates_csv}' is missing required columns. Expected columns: {required_columns}")
        st.stop()

    # Determine min/max date from CSV
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    st.subheader("Reference Data (Preview)")
    st.write("Below is a quick preview of the loaded historical data:")
    st.dataframe(df.head())

    # 3. Date Range Selection (limited to [min_date, max_date])
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
            min_value=min_date,
            max_value=max_date
        )
    with col3:
        admin_fee = st.number_input(
            "Admin Fee ($/GJ)",
            min_value=0.0,
            step=0.05,
            format="%.4f"
        )

    # 4. Monthly Consumption (Manual)
    st.header("Monthly Consumption Patterns (GJ)")
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
            format="%.2f"
        )

    # 5. Volumetric Hedge
    st.header("Volumetric Hedge")
    st.write("Define a partial fixed-rate hedge. Check the box below to enable it.")
    use_hedge = st.checkbox("Include Volumetric Hedge?")

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
            value=start_date_input,  # default to main start
            min_value=start_date_input,
            max_value=end_date_input
        )
        hedge_term_months = st.number_input("Hedge Term (months)", min_value=1, value=6)
        hedge_fixed_rate = st.number_input(
            "Hedge Fixed Rate ($/GJ)",
            min_value=0.0,
            step=0.1,
            format="%.4f"
        )

    # 6. Additional Options
    st.header("Additional Options")
    show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
    show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)

    # 7. Submit Button
    submitted = st.button("Submit", type="primary")
    if not submitted:
        st.stop()

    # ----- POST-SUBMIT LOGIC -----
    # Convert date inputs to Pandas Timestamps
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)

    # If hedge is enabled, also convert the hedge start date
    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_start_ts = None
        hedge_end_ts = None

    # 8. Filter data by user-specified date range
    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    df_filtered = df.loc[mask].copy()

    if df_filtered.empty:
        st.warning("No rate data found for the selected date range. Please adjust your dates or check your CSV.")
        st.stop()

    # 9. Aggregate monthly data (average rates in $/GJ)
    df_filtered["year_month"] = df_filtered["date"].dt.to_period("M")
    monthly_rates = (
        df_filtered
        .groupby("year_month", as_index=False)
        .agg({
            "wholesale_rate": "mean"
        })
    )
    if province == "Alberta":
        monthly_rates["utility_selected"] = df_filtered.groupby("year_month")["regulated_rate"].mean().values
    else:
        if 'local_utility_rate_egd' in df_filtered.columns and 'local_utility_rate_usouth' in df_filtered.columns:
            # Prompt user to select the local utility rate if not already done
            if 'local_utility_choice' not in st.session_state:
                st.session_state['local_utility_choice'] = "EGD"  # default choice

            if not use_hedge:  # Only prompt if not using hedge to prevent repetition
                st.write("### Select Local Utility Rate for Ontario Gas")
                local_utility_choice = st.radio(
                    "Select Ontario Gas Utility:",
                    ["EGD", "Union South"]
                )
                st.session_state['local_utility_choice'] = local_utility_choice
            else:
                local_utility_choice = st.session_state.get('local_utility_choice', "EGD")
        else:
            st.error(f"Rates file '{rates_csv}' is missing local utility rate columns.")
            st.stop()

        # Assign utility_selected based on choice
        if 'local_utility_choice' in st.session_state:
            if st.session_state['local_utility_choice'] == "EGD":
                monthly_rates["utility_selected"] = df_filtered.groupby("year_month")["local_utility_rate_egd"].mean().values
            else:
                monthly_rates["utility_selected"] = df_filtered.groupby("year_month")["local_utility_rate_usouth"].mean().values
        else:
            st.error("Local utility choice not set.")
            st.stop()

    monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
    monthly_rates.sort_values("year_month", inplace=True)
    monthly_rates.reset_index(drop=True, inplace=True)

    st.write("**Averaged monthly data (filtered by date range):**")
    st.dataframe(monthly_rates.head())

    # 10. Calculate monthly costs (in dollars)
    monthly_cost_utility = []
    monthly_cost_client = []

    for _, row in monthly_rates.iterrows():
        month_datetime = pd.Timestamp(row["year_month"])
        whl_rate = row["wholesale_rate"]  # $/GJ
        u_rate = row["utility_selected"]  # $/GJ

        mnum = month_datetime.month
        month_consumption = consumption[mnum]  # GJ

        # Utility Cost (Regulated Rate)
        cost_utility = month_consumption * u_rate  # in dollars

        # Client Cost (Wholesale + Admin Fee, partial hedge if applicable)
        if use_hedge and hedge_start_ts and (hedge_start_ts <= month_datetime < hedge_end_ts):
            # Hedge portion without admin fee
            hedged_volume = month_consumption * (hedge_portion_percent / 100.0)
            floating_volume = month_consumption - hedged_volume
            cost_hedged = hedged_volume * hedge_fixed_rate  # dollars (no admin fee)
            cost_floating = floating_volume * (whl_rate + admin_fee)  # dollars
            cost_client = cost_hedged + cost_floating
        else:
            # Fully unhedged => (wholesale + admin_fee)
            cost_client = month_consumption * (whl_rate + admin_fee)

        monthly_cost_utility.append(cost_utility)
        monthly_cost_client.append(cost_client)

    total_utility = sum(monthly_cost_utility)
    total_client = sum(monthly_cost_client)

    # 11. Reporting
    st.header("Cost Comparison Report (CAD)")
    colA, colB = st.columns(2)
    colA.metric("Utility Cost (CAD)", f"${total_utility:,.2f}")
    colB.metric("Client Cost (CAD)", f"${total_client:,.2f}")

    diff_utility_vs_client = total_utility - total_client
    st.write("### Difference in Total Cost (CAD)")
    st.write(f"**Utility - Client**: ${diff_utility_vs_client:,.2f}")

    if diff_utility_vs_client > 0:
        st.success(f"You would have saved ${diff_utility_vs_client:,.2f} by using the Client Cost (vs. Utility).")
    elif diff_utility_vs_client < 0:
        st.error(f"You would have spent ${-diff_utility_vs_client:,.2f} more by using the Client Cost (vs. Utility).")
    else:
        st.info("No difference between Utility and Client Cost.")

    # 12. Optional Monthly Breakdown
    monthly_display = []
    for idx, row in monthly_rates.iterrows():
        date_label = pd.Timestamp(row["year_month"])
        month_str = date_label.strftime("%b %Y")

        cost_util = monthly_cost_utility[idx]
        cost_client = monthly_cost_client[idx]
        diff_val = cost_util - cost_client

        monthly_data = {
            "Month": month_str,
            "Utility Cost (CAD)": cost_util,
            "Client Cost (CAD)": cost_client,
            "Diff (Utility - Client)": diff_val
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

if __name__ == "__main__":
    main()
