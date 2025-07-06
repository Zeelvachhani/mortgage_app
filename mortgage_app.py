import streamlit as st
import pandas as pd
import numpy_financial as npf
import matplotlib.pyplot as plt

st.set_page_config(page_title="Mortgage Comparison App", layout="wide")
st.title("🏠 Mortgage Loan Comparison & Refinance Simulator")

# --- Sidebar Inputs ---
st.sidebar.header("Loan A")
home_price_a = st.sidebar.number_input("Home Price", value=800000)
down_a = st.sidebar.number_input("Down Payment %", value=20.0)
rate_a = st.sidebar.number_input("Interest Rate (%)", value=6.5) / 100
term_a = st.sidebar.number_input("Loan Term (years)", value=30)
pmi_a = 0.0

st.sidebar.header("Loan B")
down_b = st.sidebar.number_input("Down Payment % (B)", value=3.51)
rate_b = st.sidebar.number_input("Interest Rate (%) (B)", value=2.05) / 100
term_b = st.sidebar.number_input("Loan Term (years) (B)", value=30)
pmi_b = st.sidebar.number_input("Monthly PMI (B)", value=129.33)

# Refinance
st.sidebar.header("Refinance Scenario for Loan A")
refi_year = st.sidebar.slider("Refinance Year", 1, 30, 5)
refi_rate = st.sidebar.number_input("New Rate After Refi (%)", value=3.0) / 100
refi_cost = st.sidebar.number_input("Refi Closing Costs ($)", value=10000)

# --- Calculations ---
def amortization_schedule(loan_amount, annual_rate, term_years, start_year=0, pmi=0, extra_costs=0):
    monthly_rate = annual_rate / 12
    months = term_years * 12
    payment = npf.pmt(monthly_rate, months, -loan_amount)
    
    schedule = []
    balance = loan_amount
    total_interest = 0
    
    for m in range(1, months + 1):
        interest = balance * monthly_rate
        principal = payment - interest
        balance -= principal
        total_interest += interest
        total_payment = payment + pmi

        schedule.append({
            "Month": m,
            "Year": start_year + (m - 1) // 12,
            "Payment": round(payment, 2),
            "Principal": round(principal, 2),
            "Interest": round(interest, 2),
            "Total Payment": round(total_payment, 2),
            "Balance": round(balance if balance > 0 else 0, 2),
            "Total Interest Paid": round(total_interest, 2),
            "PMI": pmi,
            "Extra Costs": extra_costs if m == 1 else 0
        })

    return pd.DataFrame(schedule)

# --- Loan A ---
loan_amt_a = home_price_a * (1 - down_a / 100)
loan_a = amortization_schedule(loan_amt_a, rate_a, term_a, pmi=pmi_a)

# --- Refi Loan A ---
def refinance_schedule(prev_df, new_rate, new_term_years, refi_year, closing_costs):
    balance_at_refi = prev_df[prev_df["Year"] == refi_year]["Balance"].iloc[-1]
    refi_df = amortization_schedule(balance_at_refi, new_rate, new_term_years, refi_year, extra_costs=closing_costs)
    return pd.concat([prev_df[prev_df["Year"] < refi_year], refi_df])

loan_a_refi = refinance_schedule(loan_a, refi_rate, term_a - refi_year, refi_year, refi_cost)

# --- Loan B ---
loan_amt_b = home_price_a * (1 - down_b / 100)
loan_b = amortization_schedule(loan_amt_b, rate_b, term_b, pmi=pmi_b)

# --- Summaries ---
def summarize(df, label):
    y = df.groupby("Year").agg({
        "Principal": "sum",
        "Interest": "sum",
        "Total Payment": "sum",
        "Balance": "last",
        "PMI": "sum",
        "Extra Costs": "sum"
    }).reset_index()
    y["Loan"] = label
    return y

sum_a = summarize(loan_a, "Loan A")
sum_a_refi = summarize(loan_a_refi, "Loan A Refi")
sum_b = summarize(loan_b, "Loan B")

summary = pd.concat([sum_a, sum_a_refi, sum_b])
pivot = summary.pivot(index="Year", columns="Loan", values="Balance")

# --- Display ---
st.subheader("📊 Remaining Balance by Year")
st.line_chart(pivot)

st.subheader("🧾 Yearly Summary")
st.dataframe(summary)

# --- Total Cost Calculation ---
def total_cost(df):
    return df["Total Payment"].sum() + df["Extra Costs"].sum()

st.subheader("💰 Total Cost of Loan")
st.write(f"**Loan A:** ${total_cost(loan_a):,.0f}")
st.write(f"**Loan A Refi:** ${total_cost(loan_a_refi):,.0f}")
st.write(f"**Loan B:** ${total_cost(loan_b):,.0f}")
