import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

def main():
    st.title("Market Performance Simulator (CAD)")

    st.write("""
    This tool compares:
    1. **Utility Cost** (Local Utility)
    2. **Client Cost** (Wholesale + Admin Fee)
    with an optional **Volumetric Hedge** (partial fixed rate).
    All currency is assumed to be in **CAD**.
    """)

    MONTH_NAMES = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # ----- SINGLE FORM -----
    with st.form("input_form"):
        # 1. Monthly Consumption
        st.header("Monthly Consumption Patterns (m³)")
        consumption = {}
        for i, name in enumerate(MONTH_NAMES, start=1):
            consumption[i] = st.number_input(
                f"{name}",
                min_value=0.0,
                step=1.0,
                format="%.2f"
            )

        # 2. Date Range & Admin Fee
        st.header("Date Range and Administrative Fee")
        col1, col2, col3 = st.columns(3)
        with col1:
            start_date_input = st.date_input("Start Date", value=datetime(2021, 1, 1))
        with col2:
            end_date_input = st.date_input("End Date", value=datetime(2021, 12, 31))
        with col3:
            admin_fee = st.number_input("Admin Fee (cents/m³)", min_value=0.0, step=0.1, format="%.2f")

        # 3. Zone Selector
        st.header("Zone Selection")
        zone = st.selectbox(
            "Select your zone:",
            ["EGD Zone", "Union South Zone"]
        )

        # 4. Volumetric Hedge Section
        st.header("Volumetric Hedge")
        st.write("Define a partial fixed-rate hedge. Check the box below to enable it.")
        use_hedge = st.checkbox("Include Volumetric Hedge?")

        hedge_portion_percent = 0.0
        hedge_start_date_input = None
        hedge_term_months = 0
        hedge_fixed_rate = 0.0

        if use_hedge:
            # Only show hedge inputs if user wants to include it
            hedge_portion_percent = st.number_input(
                "Hedged portion of monthly volume (%)",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                value=30.0
            )
            # Limit hedge start date to be within the main date range
            hedge_start_date_input = st.date_input(
                "Hedge Start Date",
                value=start_date_input,  # default to main start
                min_value=start_date_input,
                max_value=end_date_input
            )
            hedge_term_months = st.number_input("Hedge Term (months)", min_value=0, value=6)
            hedge_fixed_rate = st.number_input("Hedge Fixed Rate (cents/m³)", min_value=0.0, step=0.1, format="%.2f")

        # 5. Checkboxes for detailed outputs
        st.header("Additional Options")
        show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
        show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)

        # 6. Submit button
        submitted = st.form_submit_button("Submit")

    # Only run calculations after the user presses Submit
    if not submitted:
        st.info("Please fill out the form above and click Submit.")
        return

    # ----- POST-SUBMIT LOGIC -----
    # Convert date inputs to Pandas Timestamps
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)

    # If hedge is enabled, also convert the hedge start date
    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
    else:
        hedge_start_ts = None

    # 7. Load Historical Data
    csv_path = "/workspaces/blank-app/historical_data.csv"  # Adjust if needed
    try:
        df = pd.read_csv(csv_path, parse_dates=["date"])
    except FileNotFoundError:
        st.error(f"Could not find '{csv_path}'. Please ensure the file exists at that path.")
        return

    required_columns = {"date", "wholesale_rate", "local_utility_rate_egd", "local_utility_rate_usouth"}
    if not required_columns.issubset(df.columns):
        st.error(f"CSV is missing required columns. Expected columns: {required_columns}")
        return

    st.subheader("Reference Data (Preview)")
    st.dataframe(df.head())

    # 8. Filter data by user-specified date range
    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    df_filtered = df.loc[mask].copy()

    if df_filtered.empty:
        st.warning("No data found for the selected date range. Please adjust your dates or check your CSV.")
        return

    # 9. Select correct local utility column based on zone
    if zone == "EGD Zone":
        df_filtered["utility_selected"] = df_filtered["local_utility_rate_egd"]
    else:
        df_filtered["utility_selected"] = df_filtered["local_utility_rate_usouth"]

    # 10. Aggregate monthly data
    df_filtered["year_month"] = df_filtered["date"].dt.to_period("M")
    monthly_rates = (
        df_filtered
        .groupby("year_month", as_index=False)
        .agg({
            "wholesale_rate": "mean",
            "utility_selected": "mean"
        })
    )
    # Convert to Timestamp (first day of that month)
    monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
    monthly_rates.sort_values("year_month", inplace=True)
    monthly_rates.reset_index(drop=True, inplace=True)

    st.write("**Averaged monthly data (filtered by date range):**")
    st.dataframe(monthly_rates.head())

    # 11. Calculate monthly costs (in cents)
    monthly_cost_utility = []  # Utility Cost
    monthly_cost_client = []   # Client Cost (Wholesale + Admin Fee, possibly hedged)

    # Determine end of hedge window if user is using a hedge
    if use_hedge and hedge_start_ts:
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_end_ts = None

    for _, row in monthly_rates.iterrows():
        # Make sure it's a Timestamp
        month_datetime = pd.Timestamp(row["year_month"])

        w_rate = row["wholesale_rate"]          # cents/m³ (wholesale)
        utility_rate = row["utility_selected"]  # cents/m³ (local utility)
        month_num = month_datetime.month
        month_consumption = consumption[month_num]

        # 1) Utility Cost
        cost_utility = month_consumption * utility_rate
        monthly_cost_utility.append(cost_utility)

        # 2) Client Cost (Wholesale + Admin Fee, partial hedge if applicable)
        if use_hedge and (hedge_start_ts <= month_datetime < hedge_end_ts):
            # Hedge portion
            hedged_volume = month_consumption * (hedge_portion_percent / 100.0)
            floating_volume = month_consumption - hedged_volume

            # Hedged portion cost
            cost_hedged = hedged_volume * (hedge_fixed_rate + admin_fee)
            # Floating portion cost
            cost_floating = floating_volume * (w_rate + admin_fee)

            cost_client = cost_hedged + cost_floating
        else:
            # No hedge => entire volume at (wholesale + admin_fee)
            cost_client = month_consumption * (w_rate + admin_fee)

        monthly_cost_client.append(cost_client)

    # 12. Summaries in cents
    total_utility = sum(monthly_cost_utility)
    total_client = sum(monthly_cost_client)

    # Convert to dollars (CAD)
    utility_dollars = total_utility / 100
    client_dollars = total_client / 100

    # 13. Reporting
    st.header("Cost Comparison Report (CAD)")
    colA, colB = st.columns(2)

    colA.metric("Utility Cost (CAD)", f"${utility_dollars:,.2f}")
    colB.metric("Client Cost (CAD)", f"${client_dollars:,.2f}")

    diff_utility_vs_client = utility_dollars - client_dollars

    st.write("### Difference in Total Cost (CAD)")
    st.write(f"**Utility - Client**: ${diff_utility_vs_client:,.2f}")

    if diff_utility_vs_client > 0:
        st.success(f"You would have **saved** ${diff_utility_vs_client:,.2f} by using the Client Cost (vs. Utility).")
    elif diff_utility_vs_client < 0:
        st.error(f"You would have spent an **extra** ${-diff_utility_vs_client:,.2f} using the Client Cost (vs. Utility).")
    else:
        st.info("No difference between Utility and Client Cost.")

    # ----- OPTIONAL DETAILED MONTHLY RESULTS -----
    monthly_display = []
    for idx, row in monthly_rates.iterrows():
        date_label = pd.Timestamp(row["year_month"])
        month_str = date_label.strftime("%b %Y")

        cost_util = monthly_cost_utility[idx] / 100
        cost_client = monthly_cost_client[idx] / 100
        diff_val = cost_util - cost_client

        monthly_data = {
            "Month": month_str,
            "Utility Cost (CAD)": cost_util,
            "Client Cost (CAD)": cost_client,
            "Diff (Utility - Client)": diff_val
        }
        monthly_display.append(monthly_data)

    monthly_df = pd.DataFrame(monthly_display)

    # 14. Show monthly bar chart (grouped) if selected
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
            xOffset="Scenario:N"  # side-by-side grouping
        ).properties(
            width=600,
            height=400
        )

        st.altair_chart(chart, use_container_width=True)

    # 15. Show monthly cost table if selected
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

if __name__ == "__main__":
    main()
