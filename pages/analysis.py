elif user_type == "New Business":
    # --- New Business Workflow ---
    
    st.header("Market Performance Simulator (CAD) - New Business")
    
    # 2. Select Province and Commodity
    st.subheader("Select Province and Commodity")
    province = st.selectbox("Select Province:", ["Alberta", "Ontario"])
    commodity = st.selectbox("Select Commodity:", ["gas", "electricity"])
    
    # 3. Date Range Selection
    st.subheader("Date Range and Administrative Fee")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date_input = st.date_input(
            "Start Date",
            value=datetime.today().date(),
            min_value=datetime(2000, 1, 1).date()
        )
    with col2:
        end_date_input = st.date_input(
            "End Date",
            value=datetime.today().date(),
            min_value=start_date_input
        )
    with col3:
        admin_fee = st.number_input(
            "Admin Fee ($/GJ)",
            min_value=0.0,
            step=0.05,
            format="%.4f"
        )
    
    # 4. Monthly Consumption (Manual)
    st.subheader("Monthly Consumption Patterns (GJ)")
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
    st.subheader("Volumetric Hedge")
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
        hedge_term_months = st.number_input("Hedge Term (months)", min_value=1, value=6)
        hedge_fixed_rate = st.number_input(
            "Hedge Fixed Rate (All-Inclusive) ($/GJ)",
            min_value=0.0,
            step=0.1,
            format="%.4f"
        )
    
    # 6. Additional Options
    st.subheader("Additional Options")
    show_monthly_chart = st.checkbox("Show monthly bar chart of costs?", value=True)
    show_monthly_table = st.checkbox("Show monthly cost table & differences?", value=True)
    
    # 7. Submit Button
    submitted = st.button("Submit", type="primary")
    if not submitted:
        st.stop()
    
    # ----- POST-SUBMIT LOGIC FOR NEW BUSINESS -----
    # Convert date inputs to Pandas Timestamps
    start_ts = pd.to_datetime(start_date_input)
    end_ts = pd.to_datetime(end_date_input)
    
    if use_hedge and hedge_start_date_input:
        hedge_start_ts = pd.to_datetime(hedge_start_date_input)
        hedge_end_ts = hedge_start_ts + pd.DateOffset(months=int(hedge_term_months))
    else:
        hedge_start_ts = None
        hedge_end_ts = None
    
    # 8. Load Rates CSV
    rates_csv = get_rates_csv(province, commodity)
    rates_filepath = get_data_path(rates_csv)
    df_rates = load_csv(rates_filepath, {
        "date", "regulated_rate", "wholesale_rate" if province == "Alberta" else "local_utility_rate_egd", "local_utility_rate_usouth" if province == "Ontario" else "wholesale_rate"
    })
    
    # 9. Select Utility Rate
    if province == "Alberta":
        # Utility cost is the regulated_rate column
        df_rates["utility_selected"] = df_rates["regulated_rate"]
    else:
        # Ontario => EGD or Union South
        st.subheader("Select Local Utility Rate for Ontario Gas")
        local_utility_choice = st.radio(
            "Select Ontario Gas Utility:",
            ["EGD", "Union South"]
        )
        if local_utility_choice == "EGD":
            df_rates["utility_selected"] = df_rates["local_utility_rate_egd"]
        else:
            df_rates["utility_selected"] = df_rates["local_utility_rate_usouth"]
    
    # 10. Filter date range
    mask = (df_rates["date"] >= start_ts) & (df_rates["date"] <= end_ts)
    df_filtered = df_rates.loc[mask].copy()
    if df_filtered.empty:
        st.warning("No rate data in the selected date range. Please adjust your dates or check your CSV.")
        st.stop()
    
    # 11. Aggregate monthly data (average rates in $/GJ)
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
    
    # 12. Calculate monthly costs (in dollars)
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
    
    # 13. Reporting
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
    
    # 14. Optional Monthly Breakdown
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
