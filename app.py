import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from pages import current_client, new_business # Import your page files

import tkinter as tk

import streamlit as st

# Define the homepage
def app():
    # Display the title
    st.title("Steph's Gas Calc")
    
    # Add a block of text
    st.write("""
        Welcome to Steph's gas cost calculator designed to simulate 
        market performance for large volume natural gas users in Ontario!
    """)

# Run the homepage if this is the main file
if __name__ == "__main__":
    app()
