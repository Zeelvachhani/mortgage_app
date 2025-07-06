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

home_price = st.sidebar.number_input("Home Price ($)", value=800000)
total_cash = st.sidebar.number_input("Total Cash Available ($)", value=120000)
current_market_rate = st.sidebar.number_input("Current Market Interest Rate (%)", min_value=0.0, max_value=20.0, value=6.5, step=0.01) / 100
max_down_pct = st.sidebar.number_input("Max Down Payment (%)", min_value=3.0, max_value=100.0, step=1.0)
max_monthly = st.sidebar.number_input("Max Monthly Payment ($)", value=5000)
pmi_rate = st.sidebar.number_input("PMI Rate (%)", min_value=0.2, max_value=2.0, value=0.2, step=0.01) / 100
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
        current_pmi = (loan_amount * pmi_rate  / 12) if current_ltv > max_ltv else 0
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
    discount_rate_b = max(current_market_rate - 0.0025 * max_points, 0.02)
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
def valid_loan(loan_amount, monthly_payment, max_monthly, total_cash, down_payment, home_price, pmi_rate):
    if loan_amount <= 0:
        return False
    # Estimate PMI based on LTV > 80%
    pmi = loan_amount * pmi_rate if (loan_amount / home_price) > 0.80 else 0
    total_monthly = monthly_payment + pmi
    if total_monthly > max_monthly or total_monthly <= 0:
        return False
    if down_payment > total_cash:
        return False
    return True


loan_a_valid = valid_loan(loan_amount_a, monthly_payment_a, max_monthly, total_cash, down_payment_a, home_price, pmi_rate)
loan_b_valid = valid_loan(loan_amount_b, monthly_payment_b, max_monthly, total_cash, down_payment_b, home_price, pmi_rate)


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

def count_pmi_months(df):
    return (df["PMI"] > 0).sum()


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

def display_loan_details(title, home_price, down_payment, rate, discount_points, closing_cost, pmi_rate, pmi_start, monthly_payment, df):
    st.subheader(title)
    dp_pct = down_payment / home_price * 100
    pmi_months = count_pmi_months(df)
    total_monthly = monthly_payment + pmi_start

    st.markdown(f"- **Home Price**: ${home_price:,.0f}")
    st.markdown(f"- **Down Payment**: ${down_payment:,.0f} ({dp_pct:.2f}%)")
    st.markdown(f"- **Loan Amount**: ${home_price - down_payment:,.0f}")
    st.markdown(f"- **Interest Rate**: {rate * 100:.2f}%")
    st.markdown(f"- **Discount Points**: {discount_points}")
    st.markdown(f"- **Closing Cost**: ${closing_cost:,.2f}")
    st.markdown(f"- **PMI Rate**: {pmi_rate * 100:.3f}%")
    st.markdown(f"- **PMI (Monthly $ Estimate)**: ${pmi_start:,.2f}")
    st.markdown(f"- **Total Number of PMI Months**: {pmi_months}")
    st.markdown(f"- **P&I Monthly Payment**: ${monthly_payment:,.2f}")
    st.markdown(f"- **Total Monthly Payment**: ${total_monthly:,.2f}")

col1, col2 = st.columns(2)

with col1:
    pmi_a_start = (loan_amount_a * pmi_rate / 12) if (loan_amount_a / home_price) > 0.80 else 0
    display_loan_details(
        title="Loan A",
        home_price=home_price,
        down_payment=down_payment_a,
        rate=rate_a,
        discount_points=discount_points_a,
        closing_cost=extra_costs_a,
        pmi_rate=pmi_rate,
        pmi_start=pmi_a_start,
        monthly_payment=monthly_payment_a,
        df=loan_a_df
    )

with col2:
    pmi_b_start = (loan_amount_b * pmi_rate / 12) if (loan_amount_b / home_price) > 0.80 else 0
    display_loan_details(
        title="Loan B",
        home_price=home_price,
        down_payment=down_payment_b,
        rate=discount_rate_b,
        discount_points=discount_points_b,
        closing_cost=extra_costs_b,
        pmi_rate=pmi_rate,
        pmi_start=pmi_b_start,
        monthly_payment=monthly_payment_b,
        df=loan_b_df
    )


st.subheader("📊 Loan Performance Over Time")
st.dataframe(summary_final.set_index("Year"))
