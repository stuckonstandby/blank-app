import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import os
import hmac

# --- Utility Functions ---

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

def get_data_path(filename):
    """
    Returns the absolute path to a data file based on the current script's location.
    """
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, 'data')
    return os.path.join(data_dir, filename)

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

# --- Main Application ---

def main():
    # Display Logos
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
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
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

        # 3a. If Ontario + gas -> prompt EGD vs Union
        local_utility_choice = None
        if chosen_province == "Ontario" and chosen_commodity == "gas":
            local_utility_choice = st.selectbox(
                "Select Ontario Gas Utility:",
                ["EGD", "Union South"]
            )

        # 4. Aggregate vs Single Site
        st.subheader("Portfolio vs. Single Site")
        analysis_mode = st.radio(
            "Do you want to analyze the entire portfolio (aggregate) or pick a single site?",
            ["Aggregate All Sites", "Site-by-Site"]
        )

        if analysis_mode == "Aggregate All Sites":
            month_cols = ["January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"]
            earliest_start = final_subset["contract_start_date"].min()
            avg_admin_fee = final_subset["client_admin_fee"].mean()
            usage_sums = final_subset[month_cols].sum(numeric_only=True)

            month_map = {
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December"
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
            # Corrected the selectbox line below:
            chosen_site = st.selectbox("Select Site ID:", all_site_ids)

            # Additional code for handling the single site workflow would follow here...

    else:
        # --- New Business Workflow ---
        st.header("Market Performance Simulator (CAD) - New Business")
        # Your new business code would go here...

if __name__ == "__main__":
    main()
