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

    if st.session_state.get("password_correct", False):
        return True

    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()

# Actual Program
st.image("assets/portfoliopartnerslogo.png", width=800)

def main():
    st.title("Market Performance Simulator (CAD) - Existing Clients (Multi-Site)")

    st.write("""
    This tool compares:
    1. **Utility Cost** (Local Utility / Regulated Rate)
    2. **Client Cost** (Wholesale + Client's Admin Fee, with optional hedge)
    
    Hedge pricing is now **inclusive** of fees, meaning **no separate admin fee** on top of the hedge price.
    """)

    #### 1. Load the client site-level CSV ####
    csv_path_client = "client_data_by_site.csv"
    try:
        client_df = pd.read_csv(csv_path_client)
    except FileNotFoundError:
        st.error(f"Could not find '{csv_path_client}'. Please ensure it exists.")
        st.stop()

    expected_cols = {
        "client_name", "site_ID", "province", "commodity",
        "contract_start_date", "client_admin_fee",
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    }
    if not expected_cols.issubset(client_df.columns):
        st.error(f"The file '{csv_path_client}' is missing required columns: {expected_cols}")
        st.stop()

    # 1a. User picks client
    st.header("Select Client")
    all_clients = sorted(client_df["client_name"].unique())
    selected_client = st.selectbox("Select a client:", all_clients)

    # Filter to that client
    client_subset = client_df[client_df["client_name"] == selected_client].copy()
    if client_subset.empty:
        st.warning(f"No data found for client '{selected_client}'.")
        st.stop()

    # 2. Province & Commodity
    provinces_for_client = sorted(client_subset["province"].unique())
    chosen_province = st.selectbox("Select Province:", provinces_for_client)

    province_subset = client_subset[client_subset["province"] == chosen_province].copy()
    if province_subset.empty:
        st.warning(f"No data found for {selected_client} in {chosen_province}.")
        st.stop()

    commodities_for_client_prov = sorted(province_subset["commodity"].unique())
    chosen_commodity = st.selectbox("Select Commodity:", commodities_for_client_prov)

    final_subset = province_subset[province_subset["commodity"] == chosen_commodity].copy()
    if final_subset.empty:
        st.warning(f"No data found for {selected_client} in {chosen_province} with {chosen_commodity}.")
        st.stop()

    # 2a. If Ontario + gas -> prompt EGD vs Union
    local_utility_choice = None
    if chosen_province == "Ontario" and chosen_commodity == "gas":
        local_utility_choice = st.selectbox(
            "Select Ontario Gas Utility:",
            ["EGD", "Union South"]
        )

    # 3. Aggregate vs Single Site
    st.header("Portfolio vs. Single Site")
    analysis_mode = st.radio(
        "Do you want to analyze the entire portfolio (aggregate) or pick a single site?",
        ["Aggregate All Sites", "Site-by-Site"]
    )

    import numpy as np

    if analysis_mode == "Aggregate All Sites":
        month_cols = ["January","February","March","April","May","June",
                      "July","August","September","October","November","December"]
        earliest_start = final_subset["contract_start_date"].min()
        avg_admin_fee = final_subset["client_admin_fee"].mean()
        usage_sums = final_subset[month_cols].sum(numeric_only=True)

        month_map = {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
        }
        consumption = {}
        for i in range(1, 13):
            consumption[i] = float(usage_sums[month_map[i]])

        final_contract_start = earliest_start
        final_admin_fee = avg_admin_fee

        st.write(f"**Aggregated {len(final_subset)} site(s)** for {selected_client}, {chosen_province}, {chosen_commodity}.")
        st.write(f"**Earliest Contract Start**: {final_contract_start}")
        st.write(f"**Average Admin Fee**: {final_admin_fee}")
    else:
        all_site_ids = sorted(final_subset["site_ID"].unique())
        chosen_site = st.selectbox("Select Site ID:", all_site_ids)
        site_row = final_subset[final_subset["site_ID"] == chosen_site].iloc[0]

        month_map = {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
        }
        consumption = {}
        for i in range(1, 13):
            consumption[i] = float(site_row[month_map[i]])

        final_contract_start = site_row["contract_start_date"]
        final_admin_fee = site_row["client_admin_fee"]

        st.write(f"**Analyzing Site**: {chosen_site}")
        st.write(f"**Contract Start**: {final_contract_start}")
        st.write(f"**Admin Fee**: {final_admin_fee}")

    # Contract start as Timestamp
    contract_start_ts = pd.to_datetime(final_contract_start)

    # 4. Date Range
    st.header("Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date_input = st.date_input(
            "Start Date",
            value=contract_start_ts,
            min_value=contract_start_ts
        )
    with col2:
        end_date_input = st.date_input(
            "End Date",
            value=datetime(2023, 12, 31)
        )

    # 5. Volumetric Hedge
    st.header("Volumetric Hedge")
    st.write("""
    Define a partial fixed-rate hedge. Check the box below to enable it.

    **Note**: Hedge pricing here is inclusive of all fees, meaning 
    **no separate admin fee** will be added on top of the hedge price.
    """)
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
        hedge_fixed_rate = st.number_input(
            "Hedge Fixed Rate (All-Inclusive)",
            min_value=0.0,
            step=0.1,
            format="%.2f"
        )

    # Additional Options
    st.header("Additional Options")
    show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
    show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)

    # Submit
    submitted = st.button("Submit", type="primary")
    if not submitted:
        st.stop()

    # Post-submit
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)

    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_start_ts = None
        hedge_end_ts = None

    # 6. Pick the appropriate CSV
    def get_rates_csv(province, commodity):
        if province == "Alberta" and commodity == "gas":
            return "historical_data_AB_gas.csv"
        elif province == "Alberta" and commodity == "electricity":
            return "historical_data_AB_ele.csv"
        elif province == "Ontario" and commodity == "gas":
            return "historical_data_ON_gas.csv"
        else:
            st.error(f"No rate file rule for province={province}, commodity={commodity}")
            st.stop()

    rates_csv = get_rates_csv(chosen_province, chosen_commodity)
    try:
        df_rates = pd.read_csv(rates_csv, parse_dates=["date"])
    except FileNotFoundError:
        st.error(f"Could not find rates file '{rates_csv}'. Check your files.")
        st.stop()

    # Alberta: date, regulated_rate, wholesale_rate
    # Ontario: date, wholesale_rate, local_utility_rate_egd, local_utility_rate_usouth
    if chosen_province == "Alberta":
        needed_cols = {"date","regulated_rate","wholesale_rate"}
        if not needed_cols.issubset(df_rates.columns):
            st.error(f"Rates file '{rates_csv}' must have columns: {needed_cols}")
            st.stop()
    else:
        # Ontario
        needed_cols = {"date","wholesale_rate","local_utility_rate_egd","local_utility_rate_usouth"}
        if not needed_cols.issubset(df_rates.columns):
            st.error(f"Rates file '{rates_csv}' must have columns: {needed_cols}")
            st.stop()

    st.subheader("Reference Data (Preview)")
    st.dataframe(df_rates.head())

    # Filter date range
    mask = (df_rates["date"] >= start_ts) & (df_rates["date"] <= end_ts)
    df_filtered = df_rates.loc[mask].copy()
    if df_filtered.empty:
        st.warning("No rate data in that date range.")
        st.stop()

    # Build "utility_selected"
    if chosen_province == "Alberta":
        # Utility cost is the regulated_rate column
        df_filtered["utility_selected"] = df_filtered["regulated_rate"]
    else:
        # Ontario => EGD or Union
        if not local_utility_choice:
            st.error("Ontario gas requires selecting EGD or Union South.")
            st.stop()
        if local_utility_choice == "EGD":
            df_filtered["utility_selected"] = df_filtered["local_utility_rate_egd"]
        else:
            df_filtered["utility_selected"] = df_filtered["local_utility_rate_usouth"]

    # Group monthly
    df_filtered["year_month"] = df_filtered["date"].dt.to_period("M")
    monthly_rates = (
        df_filtered
        .groupby("year_month", as_index=False)
        .agg({
            "wholesale_rate": "mean",
            "utility_selected": "mean"
        })
    )
    monthly_rates["year_month"] = monthly_rates["year_month"].apply(lambda x: x.start_time)
    monthly_rates.sort_values("year_month", inplace=True)
    monthly_rates.reset_index(drop=True, inplace=True)

    st.write("**Averaged monthly data (filtered by date range):**")
    st.dataframe(monthly_rates.head())

    # Convert usage * rate to CAD, depends on AB vs ON, gas vs electricity
    def cost_in_cad(usage_value, rate_value, province, commodity):
        # AB gas => $/GJ => usage * rate
        # AB ele => cents/kWh => usage * (rate / 100)
        # ON gas => cents/m³ => usage * (rate / 100)
        if province == "Alberta" and commodity == "gas":
            return usage_value * rate_value
        elif province == "Alberta" and commodity == "electricity":
            return usage_value * (rate_value / 100.0)
        elif province == "Ontario" and commodity == "gas":
            return usage_value * (rate_value / 100.0)
        else:
            st.error(f"No cost calc rule for {province}, {commodity}")
            st.stop()

    monthly_cost_utility = []
    monthly_cost_client = []

    for _, row_m in monthly_rates.iterrows():
        month_dt = row_m["year_month"]
        w_rate = row_m["wholesale_rate"]
        u_rate = row_m["utility_selected"]

        mnum = pd.Timestamp(month_dt).month
        usage_val = consumption[mnum]

        # Utility cost => usage * utility rate
        util_cost = cost_in_cad(usage_val, u_rate, chosen_province, chosen_commodity)

        # Client cost => portion hedged at (hedge_fixed_rate, no admin fee),
        #                remainder at (w_rate + admin_fee)
        if use_hedge and hedge_start_ts and (hedge_start_ts <= month_dt < hedge_end_ts):
            # hedged portion
            hedged_vol = usage_val * (hedge_portion_percent / 100.0)
            floating_vol = usage_val - hedged_vol

            # Hedge is all-in, no admin fee added
            cost_hedged = cost_in_cad(hedged_vol, hedge_fixed_rate, chosen_province, chosen_commodity)

            # Unhedged => (wholesale + admin_fee)
            cost_floating = cost_in_cad(floating_vol, w_rate + final_admin_fee, chosen_province, chosen_commodity)

            c_cost = cost_hedged + cost_floating
        else:
            # fully unhedged => (wholesale + admin_fee)
            combined = w_rate + final_admin_fee
            c_cost = cost_in_cad(usage_val, combined, chosen_province, chosen_commodity)

        monthly_cost_utility.append(util_cost)
        monthly_cost_client.append(c_cost)

    total_utility = sum(monthly_cost_utility)
    total_client = sum(monthly_cost_client)

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

    # Prepare monthly breakdown
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

if __name__ == "__main__":
    main()
