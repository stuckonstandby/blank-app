import streamlit as st
import pandas as pd
import datetime
import re

# Ensure required dependency is installed
try:
    import openpyxl
except ImportError:
    st.error("Missing optional dependency 'openpyxl'. Install it using: pip install openpyxl")

# Streamlit App Title
st.title("Consumption Data Standardization")

# CSV path
client_csv_path = "client_data_by_site.csv"

# 1) Load existing CSV
try:
    existing_clients_df = pd.read_csv(client_csv_path)
except FileNotFoundError:
    st.error(f"Could not find the file '{client_csv_path}'. Please ensure it exists.")
    st.stop()
except Exception as e:
    st.error(f"Error reading '{client_csv_path}': {e}")
    st.stop()

# Ensure the CSV has the columns we expect:
required_cols = {"client_name", "contract_start_date", "client_admin_fee", "province", "commodity"}
missing_cols = required_cols - set(existing_clients_df.columns)
if missing_cols:
    st.error(
        f"The file '{client_csv_path}' must contain these columns: {required_cols}. "
        f"Missing columns: {missing_cols}"
    )
    st.stop()

# 2) Ensure we have a site_ID column in the CSV
if "site_ID" not in existing_clients_df.columns:
    existing_clients_df["site_ID"] = None

# Build a dictionary from account_number → site_ID for all existing data
site_mapping = {}
for _, row in existing_clients_df.dropna(subset=["site_ID"]).iterrows():
    site_mapping[row["account_number"]] = row["site_ID"]

# Determine the highest numeric portion used so far to keep incrementing
max_used_site_number = 0
for sID in site_mapping.values():
    # Attempt to parse out the integer portion from "Site 001", "Site 0123", etc.
    match = re.search(r"Site\s+(\d+)", str(sID))
    if match:
        num = int(match.group(1))
        max_used_site_number = max(max_used_site_number, num)

# 3) File upload for new consumption data
uploaded_file = st.file_uploader("Upload an Excel file (xlsx format)", type=["xlsx"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file, engine='openpyxl')
        df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
    except Exception as e:
        st.error(f"Error reading the uploaded Excel file or sheet: {e}")
        st.stop()
    
    if len(df.columns) < 3:
        st.error("The uploaded file does not have enough columns. "
                 "Please ensure it has at least three columns (account_number, date, volume).")
    else:
        # 3a) Clean up the columns
        df_cleaned = df.iloc[:, :3].copy()
        df_cleaned.columns = ["account_number", "date", "volume"]
        
        df_cleaned["date"] = pd.to_datetime(df_cleaned["date"], errors="coerce")
        df_cleaned["volume"] = pd.to_numeric(df_cleaned["volume"], errors="coerce")
        
        df_cleaned["month"] = df_cleaned["date"].dt.strftime("%B")
        df_cleaned["year"] = df_cleaned["date"].dt.year
        
        # Sort to keep the most recent entry by account_number + date
        df_cleaned.sort_values(by=["account_number", "date"], ascending=[True, False], inplace=True)
        
        # Drop duplicates per (account_number, month)
        df_deduplicated = df_cleaned.drop_duplicates(subset=["account_number", "month"], keep='first')
        
        # Pivot
        df_pivoted = df_deduplicated.pivot_table(
            index=["account_number"], 
            columns="month", 
            values="volume", 
            aggfunc="sum"
        ).reset_index()
        
        month_order = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ]
        for m in month_order:
            if m not in df_pivoted.columns:
                df_pivoted[m] = None
        
        df_pivoted = df_pivoted[["account_number"] + month_order]
        
        # 3b) Prompt user to pick province & commodity
        province = st.selectbox("Select Province", ["Ontario", "Alberta", "Quebec"])
        commodity = st.selectbox("Select Commodity", ["electricity", "natural gas"])
        
        # 3c) Also pick the client_name from existing
        client_names = existing_clients_df["client_name"].unique().tolist()
        selected_client_name = st.selectbox("Select Existing Client Name", client_names)
        
        # Retrieve contract details for that client
        client_row = existing_clients_df.loc[
            existing_clients_df["client_name"] == selected_client_name
        ].iloc[0]
        contract_start_date = client_row["contract_start_date"]
        client_admin_fee = client_row["client_admin_fee"]
        
        # 3d) Build final dataframe
        df_pivoted["client_name"] = selected_client_name
        df_pivoted["contract_start_date"] = contract_start_date
        df_pivoted["client_admin_fee"] = client_admin_fee
        df_pivoted["data_as_of"] = datetime.date.today().strftime("%Y-%m-%d")
        
        df_pivoted["province"] = province
        df_pivoted["commodity"] = commodity
        
        # 3e) Assign/re-use site_ID
        new_site_IDs = []
        for acc in df_pivoted["account_number"]:
            if acc in site_mapping:
                new_site_IDs.append(site_mapping[acc])
            else:
                max_used_site_number += 1
                new_sID = f"Site {max_used_site_number:03d}"
                site_mapping[acc] = new_sID
                new_site_IDs.append(new_sID)
        df_pivoted["site_ID"] = new_site_IDs
        
        final_columns = [
            "client_name",
            "site_ID",
            "account_number",
            "contract_start_date",
            "client_admin_fee",
            "province",
            "commodity",
            "data_as_of"
        ] + month_order
        
        df_final = df_pivoted[final_columns]
        
        # Show final
        st.write("### Processed Data")
        st.dataframe(df_final)
        
        # Offer download
        csv_content = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Processed CSV", 
            csv_content, 
            "cleaned_consumption_data.csv", 
            "text/csv"
        )
        
        # Optionally append back to CSV
        st.write("### Append to Existing CSV")
        if st.button("Append Data to client_data_by_site.csv"):
            try:
                # Reload to ensure fresh
                existing_data = pd.read_csv(client_csv_path)
                if "site_ID" not in existing_data.columns:
                    existing_data["site_ID"] = None
                
                combined_df = pd.concat([existing_data, df_final], ignore_index=True)
                
                # (Optional) remove duplicates if you want
                # combined_df.drop_duplicates(
                #     subset=[
                #         "client_name", "account_number", 
                #         "contract_start_date", "data_as_of", 
                #         "province", "commodity"
                #     ],
                #     keep='first',
                #     inplace=True
                # )
                
                combined_df.to_csv(client_csv_path, index=False)
                st.success(f"Data appended to '{client_csv_path}' successfully!")
            except Exception as e:
                st.error(f"Failed to append to '{client_csv_path}': {e}")
