import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

import hmac

## checks password

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# Actual Program

st.image("assets/portfoliopartnerslogo.png", width=800)

def main():
    st.title("Market Performance Simulator (CAD) - Single Client from CSV")

    st.write("""
    This tool compares:
    1. **Utility Cost** (Local Utility)
    2. **Client Cost** (Wholesale + Admin Fee)
    with an optional **Volumetric Hedge** (partial fixed rate).
    
    **Monthly consumption** is loaded from a CSV for **one client**.
    """)

    # 1. Load the client consumption CSV
    csv_path_client = "client_consumption_data.csv"  # Adjust path if needed
    try:
        client_df = pd.read_csv(csv_path_client)
    except FileNotFoundError:
        st.error(f"Could not find '{csv_path_client}'. Please ensure it exists.")
        st.stop()

    # Validate columns. We assume each client has exactly one row (no multi-site).
    expected_cols = {
        "client_name",
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    }
    if not expected_cols.issubset(client_df.columns):
        st.error(f"The file '{csv_path_client}' is missing required columns for monthly consumption.")
        st.stop()

    # 2. User picks which client to load
    st.header("Select Client from CSV")
    client_list = sorted(client_df["client_name"].unique().tolist())
    selected_client = st.selectbox("Select a client:", client_list)

    # Now find that row (assuming each client_name is unique or just take the first match)
    row = client_df[client_df["client_name"] == selected_client].iloc[0]

    # Build the consumption dictionary
    month_map = {
        1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
        7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
    }
    consumption = {}
    for i in range(1, 13):
        consumption[i] = float(row[month_map[i]])

    st.info(f"Loaded monthly consumption for client: {selected_client}")

    # 3. Date Range & Admin Fee
    st.header("Date Range and Administrative Fee")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date_input = st.date_input("Start Date", value=datetime(2021, 1, 1))
    with col2:
        end_date_input = st.date_input("End Date", value=datetime(2021, 12, 31))
    with col3:
        admin_fee = st.number_input("Admin Fee (cents/m³)", min_value=0.0, step=0.1, format="%.2f")

    # 4. Zone Selection
    st.header("Zone Selection")
    zone = st.selectbox(
        "Select your zone:",
        ["EGD Zone", "Union South Zone"]
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
            value=start_date_input,
            min_value=start_date_input,
            max_value=end_date_input
        )
        hedge_term_months = st.number_input("Hedge Term (months)", min_value=0, value=6)
        hedge_fixed_rate = st.number_input("Hedge Fixed Rate (cents/m³)", min_value=0.0, step=0.1, format="%.2f")

    # 6. Additional Options
    st.header("Additional Options")
    show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
    show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)

    # 7. Submit button
    submitted = st.button("Submit", type="primary")

    if not submitted:
        st.stop()

    # ----- POST-SUBMIT LOGIC -----
    # Convert date inputs to Pandas Timestamps
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)

    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_start_ts = None
        hedge_end_ts = None

    # 8. Load Historical Rate Data
    csv_path_rates = "/workspaces/blank-app/historical_data.csv"
    try:
        df = pd.read_csv(csv_path_rates, parse_dates=["date"])
    except FileNotFoundError:
        st.error(f"Could not find '{csv_path_rates}'. Please ensure the file exists at that path.")
        st.stop()

    required_columns = {"date", "wholesale_rate", "local_utility_rate_egd", "local_utility_rate_usouth"}
    if not required_columns.issubset(df.columns):
        st.error(f"CSV is missing required columns. Expected columns: {required_columns}")
        st.stop()

    st.subheader("Reference Data (Preview)")
    st.dataframe(df.head())

    # 9. Filter data by user-specified date range
    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    df_filtered = df.loc[mask].copy()

    if df_filtered.empty:
        st.warning("No rate data found for the selected date range. Please adjust your dates or check your CSV.")
        st.stop()

    # 10. Select correct local utility column based on zone
    if zone == "EGD Zone":
        df_filtered["utility_selected"] = df_filtered["local_utility_rate_egd"]
    else:
        df_filtered["utility_selected"] = df_filtered["local_utility_rate_usouth"]

    # 11. Aggregate monthly data (rates)
    df_filtered["year_month"] = df_filtered["date"].dt.to_period("M")
    monthly_rates = (
        df_filtered
        .groupby("year_month", as_index=False)
        .agg({
            "wholesale_rate": "mean",
            "utility_selected": "mean"
        })
    )
    # Convert to Timestamp
    monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
    monthly_rates.sort_values("year_month", inplace=True)
    monthly_rates.reset_index(drop=True, inplace=True)

    st.write("**Averaged monthly data (filtered by date range):**")
    st.dataframe(monthly_rates.head())

    # 12. Calculate monthly costs (in cents)
    monthly_cost_utility = []
    monthly_cost_client = []

    for _, row2 in monthly_rates.iterrows():
        month_datetime = pd.Timestamp(row2["year_month"])
        w_rate = row2["wholesale_rate"]
        utility_rate = row2["utility_selected"]

        mnum = month_datetime.month
        month_consumption = consumption[mnum]

        # Utility Cost
        cost_utility = month_consumption * utility_rate

        # Client Cost (Wholesale + Admin Fee, partial hedge if applicable)
        if use_hedge and hedge_start_ts and (hedge_start_ts <= month_datetime < hedge_end_ts):
            hedged_volume = month_consumption * (hedge_portion_percent / 100.0)
            floating_volume = month_consumption - hedged_volume

            cost_hedged = hedged_volume * (hedge_fixed_rate + admin_fee)
            cost_floating = floating_volume * (w_rate + admin_fee)

            cost_client = cost_hedged + cost_floating
        else:
            cost_client = month_consumption * (w_rate + admin_fee)

        monthly_cost_utility.append(cost_utility)
        monthly_cost_client.append(cost_client)

    # Summaries in cents
    total_utility = sum(monthly_cost_utility)
    total_client = sum(monthly_cost_client)

    # Convert to dollars
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
        st.success(f"You would have saved ${diff_utility_vs_client:,.2f} by using the Client Cost (vs. Utility).")
    elif diff_utility_vs_client < 0:
        st.error(f"You would have spent ${-diff_utility_vs_client:,.2f} more by using the Client Cost (vs. Utility).")
    else:
        st.info("No difference between Utility and Client Cost.")

    # ----- OPTIONAL DETAILED MONTHLY RESULTS -----
    monthly_display = []
    for idx, row2 in monthly_rates.iterrows():
        date_label = pd.Timestamp(row2["year_month"])
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
            xOffset="Scenario:N"
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
