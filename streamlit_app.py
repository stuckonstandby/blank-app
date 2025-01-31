# Import necessary libraries
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from pages import current_client, new_business_on_gas

# Set the title of the app
st.title("Steph's Simulation Calc")

# Display the welcome message
st.write(
    "Welcome to Steph's gas cost calculator designed to simulate market performance for large volume energy users in Canada!"
)

# (Optional) Add navigation or additional content here
# For example, you can add buttons to navigate to different pages
# st.sidebar.success("Select a page above.")

if __name__ == "__main__":
    app()
