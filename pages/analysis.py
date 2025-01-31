# Import necessary libraries
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import os
import hmac

# --- Utility Functions ---

def get_data_path(filename):
    """
    Returns the absolute path to a data file based on the current script's location.
    """
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, 'data')
    return os.path.join(data_dir, filename)

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

def load_csv(filepath, required_columns):
    """
    Loads a CSV file and checks for required columns.
    """
    if not os.path.exists(filepath):
        st.error(f"Could not find '{os.path.basename(filepath)}' in the data directory. Please ensure the file exists.")
        st.stop()
    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
    except Exception as e:
        st.error(f"Error reading the CSV file: {e}")
        st.stop()
    if not required_columns.issubset(df.columns):
        st.error(f"CSV '{os.path.basename(filepath)}' is missing required columns. Expected columns: {required_columns}")
        st.stop()
    return df

def check_password():
    """
    Returns `True` if the user had the correct password.
    """
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["PASSWORD"]):
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

# --- Main Application ---

def main():
    # Display logos
    st.image("assets/capitalmarketslogo.png", width=400)
    st.title("Market Performance Simulator (CAD)")

    # 1. Select User Type
    user_type = st.radio(
        "Are you a Current Client or New Business?",
        ("Current Client", "New Business")
    )

    if user_type == "Current Client":
        # --- Current Client Workflow ---

        # Prompt for password
        if not check_password():
            st.stop()

        # Load client data
        client_csv = get_data_path("client_data_by_site.csv")
        client_df = load_csv(client_csv, {
            "client_name", "site_ID", "province", "commodity",
            "contract_start_date", "client_admin_fee",
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        })

        st.image("assets/portfoliopartnerslogo.png", width=800)
        st.header("Market Performance Simulator (CAD) - Existing Clients (Multi-Site)")

        # 2. User picks client
        st.subheader("Select Client")
        all_clients = sorted(client_df["client_name"].unique())
        selected_client = st.selectbox("Select a client:", all_clients)

        # Filter to that client
        client_subset = client_df[client_df["client_name"] == selected_client].copy()
        if client_subset.empty:
            st.warning(f"No data found for client '{selected_client}'.")
            st.stop()

        # 3. Province & Commodity
        st.subheader("Select Province & Commodity")
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

        # 4. Aggregate vs Single Site
        st.subheader("Portfolio vs. Single Site")
        analysis_mode = st.radio(
            "Do you want to analyze the entire portfolio (aggregate) or pick a single site?",
            ["Aggregate All Sites", "Site-by-Site"]
        )

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

        # 5. Date Range
        st.subheader("Date Range")
        col1, col2 = st.columns(2)
        with col1:
            start_date_input = st.date_input(
                "Start Date",
                value=contract_start_ts.date(),
                min_value=contract_start_ts.date()
            )
        with col2:
            end_date_input = st.date_input(
                "End Date",
                value=datetime(2023, 12, 31).date(),
                min_value=contract_start_ts.date()
            )

        # 6. Volumetric Hedge
        st.subheader("Volumetric Hedge")
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
            hedge_term_months = st.number_input("Hedge Term (months)", min_value=1, value=6)
            hedge_fixed_rate = st.number_input(
                "Hedge Fixed Rate (All-Inclusive) ($/GJ)",
                min_value=0.0,
                step=0.1,
                format="%.4f"
            )

        # 7. Additional Options
        st.subheader("Additional Options")
        show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
        show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)

        # 8. Submit Button
        submitted = st.button("Submit", type="primary")
        if not submitted:
            st.stop()

        # ----- POST-SUBMIT LOGIC FOR CURRENT CLIENT ---
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

        # 9. Pick the appropriate CSV
        rates_csv = get_rates_csv(chosen_province, chosen_commodity)
        rates_filepath = get_data_path(rates_csv)
        if chosen_province == "Alberta":
            df_rates = load_csv(rates_filepath, {
                "date", "regulated_rate", "wholesale_rate"
            })
        else:
            df_rates = load_csv(rates_filepath, {
                "date", "wholesale_rate", "local_utility_rate_egd", "local_utility_rate_usouth"
            })

        st.subheader("Reference Data (Preview)")
        st.dataframe(df_rates.head())

        # 10. Filter date range
        mask = (df_rates["date"] >= start_ts) & (df_rates["date"] <= end_ts)
        df_filtered = df_rates.loc[mask].copy()
        if df_filtered.empty:
            st.warning("No rate data in the selected date range. Please adjust your dates or check your CSV.")
            st.stop()

        # 11. Select Utility Rate
        if chosen_province == "Alberta":
            # Utility cost is the regulated_rate column
            df_filtered["utility_selected"] = df_filtered["regulated_rate"]
        else:
            # Ontario => EGD or Union South
            st.subheader("Select Local Utility Rate for Ontario Gas")
            local_utility_choice = st.radio(
                "Select Ontario Gas Utility:",
                ["EGD", "Union South"]
            )
            if local_utility_choice == "EGD":
                df_filtered["utility_selected"] = df_filtered["local_utility_rate_egd"]
            else:
                df_filtered["utility_selected"] = df_filtered["local_utility_rate_usouth"]

        # 12. Aggregate monthly data (average rates in $/GJ)
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

        # 13. Calculate monthly costs (in dollars)
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
                cost_floating = floating_volume * (whl_rate + final_admin_fee)  # dollars
                cost_client = cost_hedged + cost_floating
            else:
                # Fully unhedged => (wholesale + admin_fee)
                cost_client = month_consumption * (whl_rate + final_admin_fee)

            monthly_cost_utility.append(cost_utility)
            monthly_cost_client.append(cost_client)

        total_utility = sum(monthly_cost_utility)
        total_client = sum(monthly_cost_client)

        # 14. Reporting
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

        # 15. Optional Monthly Breakdown
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
