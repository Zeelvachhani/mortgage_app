import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf

# -------------------------------
# Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="Mortgage Loan Comparison", layout="wide")
st.title("🏡 Mortgage Loan Comparison + Refinance Planner")

# -------------------------------
# Sidebar Input Constraints
# -------------------------------
st.sidebar.header("🔍 Input Constraints")

total_cash = st.sidebar.number_input("Total Cash Available ($)", value=120000)
max_monthly = st.sidebar.number_input("Max Monthly Payment ($)", value=5000)
max_down_pct = st.sidebar.slider("Max Down Payment (%)", 3.0, 100.0, 25.0)
home_price = st.sidebar.number_input("Home Price ($)", value=800000)
pmi_rate = st.sidebar.number_input("PMI Rate (%)", min_value=0.0, value=0.5, step=0.01) / 100
manual_override = st.sidebar.checkbox("🔧 Manually Enter Loan A and Loan B?")

# -------------------------------
# Loan Schedule with PMI logic
# -------------------------------
def amortization_schedule(loan_amount, annual_rate, term_years, home_price, start_year=0, pmi_rate=0, extra_costs=0):
    monthly_rate = annual_rate / 12
    months = term_years * 12
    payment = npf.pmt(monthly_rate, months, -loan_amount)

    schedule = []
    balance = loan_amount
    total_interest = 0
    max_ltv = 0.80

    for m in range(1, months + 1):
        interest = balance * monthly_rate
        principal = payment - interest
        balance -= principal
        total_interest += interest

        current_ltv = balance / home_price
        # PMI only applies if LTV > 80%
        current_pmi = loan_amount * pmi_rate if current_ltv > max_ltv else 0
        total_payment = payment + current_pmi

        schedule.append({
            "Month": m,
            "Year": start_year + (m - 1) // 12,
            "Payment": round(payment, 2),
            "Principal": round(principal, 2),
            "Interest": round(interest, 2),
            "Total Payment": round(total_payment, 2),
            "Balance": round(balance if balance > 0 else 0, 2),
            "Total Interest Paid": round(total_interest, 2),
            "PMI": round(current_pmi, 2),
            "Extra Costs": extra_costs if m == 1 else 0
        })

    return pd.DataFrame(schedule)

# -------------------------------
# Auto-Generate Loan A and B or Manual Input
# -------------------------------
term_years = 30
months = term_years * 12

if not manual_override:
    # --- Loan A ---
    down_payment_a = min(home_price * max_down_pct / 100, total_cash)
    loan_amount_a = home_price - down_payment_a
    rate_a = 0.065
    monthly_rate_a = rate_a / 12
    monthly_payment_a = npf.pmt(monthly_rate_a, months, -loan_amount_a)
    discount_points_a = 0
    extra_costs_a = 0

    # --- Loan B ---
    min_down_b = max(home_price * 0.0351, home_price * 0.03)
    loan_amount_b = home_price - min_down_b
    available_for_points = total_cash - min_down_b
    point_cost = loan_amount_b * 0.01
    max_points = int(available_for_points // point_cost) if point_cost > 0 else 0
    discount_rate_b = 0.065 - 0.0025 * max_points if max_points > 0 else 0.065
    monthly_rate_b = discount_rate_b / 12
    monthly_payment_b = npf.pmt(monthly_rate_b, months, -loan_amount_b)
    discount_points_b = max_points
    extra_costs_b = point_cost * max_points if max_points > 0 else 0
    down_payment_b = min_down_b

else:
    st.sidebar.header("Manual Loan A")
    down_payment_a = st.sidebar.number_input("Down Payment A ($)", value=160000)
    rate_a = st.sidebar.number_input("Interest Rate A (%)", value=6.5) / 100
    loan_amount_a = home_price - down_payment_a
    monthly_payment_a = npf.pmt(rate_a / 12, months, -loan_amount_a)
    discount_points_a = 0
    extra_costs_a = 0

    st.sidebar.header("Manual Loan B")
    down_payment_b = st.sidebar.number_input("Down Payment B ($)", value=28080.0)
    rate_b = st.sidebar.number_input("Interest Rate B (%)", value=2.05) / 100
    loan_amount_b = home_price - down_payment_b
    discount_points_b = st.sidebar.number_input("Discount Points B", value=17)
    extra_costs_b = loan_amount_b * (discount_points_b * 0.01)
    monthly_payment_b = npf.pmt(rate_b / 12, months, -loan_amount_b)
    discount_rate_b = rate_b

# -------------------------------
# Validate Inputs - Show No Scenario if invalid
# -------------------------------
def valid_loan(loan_amount, monthly_payment, max_monthly, total_cash, down_payment):
    # Basic validations - loan amount, payment positive and monthly below max, down payment below cash
    if loan_amount <= 0:
        return False
    if monthly_payment <= 0 or monthly_payment > max_monthly:
        return False
    if down_payment > total_cash:
        return False
    return True

loan_a_valid = valid_loan(loan_amount_a, monthly_payment_a, max_monthly, total_cash, down_payment_a)
loan_b_valid = valid_loan(loan_amount_b, monthly_payment_b, max_monthly, total_cash, down_payment_b)

if not loan_a_valid or not loan_b_valid:
    st.error("⚠️ No scenario found for one or both loans with the current inputs.")
    st.stop()

# -------------------------------
# Calculate Amortization
# -------------------------------
loan_a_df = amortization_schedule(
    loan_amount=loan_amount_a,
    annual_rate=rate_a,
    term_years=term_years,
    home_price=home_price,
    pmi_rate=pmi_rate,
    extra_costs=extra_costs_a
)

loan_b_df = amortization_schedule(
    loan_amount=loan_amount_b,
    annual_rate=discount_rate_b,
    term_years=term_years,
    home_price=home_price,
    pmi_rate=pmi_rate,
    extra_costs=extra_costs_b
)

# -------------------------------
# Generate Summary Data
# -------------------------------
def get_summary_points(df, years=[3, 5, 10, 15, 30]):
    result = []
    for yr in years:
        slice_df = df[df["Year"] < yr]
        total_payment = slice_df["Total Payment"].sum()
        total_interest = slice_df["Interest"].sum()
        remaining_balance = df[df["Year"] == yr]["Balance"].iloc[-1] if yr in df["Year"].values else 0
        result.append({
            "Year": f"{yr} Years",
            "Total Payment": round(total_payment),
            "Total Interest": round(total_interest),
            "Remaining Balance": round(remaining_balance)
        })
    return pd.DataFrame(result)

summary_a = get_summary_points(loan_a_df)
summary_b = get_summary_points(loan_b_df)

summary_final = summary_a.copy()
summary_final["Loan A: Total Payment"] = summary_final.pop("Total Payment")
summary_final["Loan A: Interest"] = summary_a["Total Interest"]
summary_final["Loan A: Balance"] = summary_a["Remaining Balance"]
summary_final["Loan B: Total Payment"] = summary_b["Total Payment"]
summary_final["Loan B: Interest"] = summary_b["Total Interest"]
summary_final["Loan B: Balance"] = summary_b["Remaining Balance"]

# -------------------------------
# Display Results
# -------------------------------
st.header("📋 Loan Comparison Summary")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Loan A")
    st.markdown(f"- **Down Payment**: ${down_payment_a:,.0f}")
    st.markdown(f"- **Loan Amount**: ${loan_amount_a:,.0f}")
    st.markdown(f"- **Interest Rate**: {rate_a * 100:.2f}%")
    st.markdown(f"- **Discount Points**: {discount_points_a}")
    st.markdown(f"- **PMI Rate**: {pmi_rate*100:.3f}%")
    # Calculate and show PMI for Loan A at start (if applicable)
    pmi_a_start = loan_amount_a * pmi_rate if (loan_amount_a / home_price) > 0.80 else 0
    st.markdown(f"- **PMI (monthly $ estimate)**: ${pmi_a_start:,.2f}")
    st.markdown(f"- **Monthly Payment (P&I)**: ${monthly_payment_a:,.2f}")

with col2:
    st.subheader("Loan B")
    st.markdown(f"- **Down Payment**: ${down_payment_b:,.0f}")
    st.markdown(f"- **Loan Amount**: ${loan_amount_b:,.0f}")
    st.markdown(f"- **Interest Rate**: {discount_rate_b * 100:.2f}%")
    st.markdown(f"- **Discount Points**: {discount_points_b}")
    st.markdown(f"- **PMI Rate**: {pmi_rate*100:.3f}%")
    pmi_b_start = loan_amount_b * pmi_rate if (loan_amount_b / home_price) > 0.80 else 0
    st.markdown(f"- **PMI (monthly $ estimate)**: ${pmi_b_start:,.2f}")
    st.markdown(f"- **Monthly Payment (P&I)**: ${monthly_payment_b:,.2f}")

st.subheader("📊 Loan Performance Over Time")
st.dataframe(summary_final.set_index("Year"))
