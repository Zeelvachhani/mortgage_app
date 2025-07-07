import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf

# -------------------------------
# Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="Mortgage Loan Comparison", layout="wide")
st.title("🏡 Mortgage Loan Comparison")

# -------------------------------
# Sidebar Input Constraints
# -------------------------------
st.sidebar.header("🔍 Input Constraints")

home_price = st.sidebar.number_input("Home Price ($)", min_value=0, step=10000)
total_cash = st.sidebar.number_input("Total Cash Available ($)", min_value=0, step=10000)
current_market_rate = st.sidebar.number_input("Current Market Interest Rate (%)", min_value=0.0, max_value=20.0, step=0.01) / 100
max_down_pct = st.sidebar.number_input("Max Down Payment (%)", min_value=0.0, max_value=100.0, step=1.0)
max_monthly = st.sidebar.number_input("Max Monthly Payment ($)", min_value=0)
pmi_rate = st.sidebar.number_input("PMI Rate (%)", min_value=0.2, max_value=2.0, step=0.01) / 100
manual_override = st.sidebar.checkbox("🔧 Manually Enter Loan A and Loan B?")

# -------------------------------
# Validate Inputs - Show No Scenario if invalid
# -------------------------------
def valid_loan(loan_amount, monthly_payment, max_monthly, total_cash, down_payment, home_price, pmi_rate):
    if loan_amount <= 0:
        return False
    pmi = (loan_amount * pmi_rate) / 12 if (loan_amount / home_price) > 0.80 else 0
    total_monthly = monthly_payment + pmi
    if total_monthly > max_monthly or total_monthly <= 0:
        return False
    if down_payment > total_cash:
        return False
    return True

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
        current_pmi = (loan_amount * pmi_rate / 12) if current_ltv > max_ltv else 0
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

def find_best_loan_a(home_price, max_down_pct, total_cash, max_monthly, pmi_rate, base_rate, term_years, point_rate_reduction=0.0025, max_points_allowed=20):
    if not (home_price and max_down_pct and total_cash and max_monthly):
        return None
        
    months = term_years * 12
    max_down_payment = min(home_price * max_down_pct / 100, total_cash)
    min_down_payment = home_price * 0.03
    step = 1000

    best_config = None

    for dp in range(int(max_down_payment), int(min_down_payment) - 1, -step):
        loan_amount = home_price - dp
        available_cash_for_points = total_cash - dp

        for points in range(0, max_points_allowed + 1):
            point_cost = loan_amount * (points * 0.01)
            if point_cost > available_cash_for_points:
                continue

            rate = base_rate - (point_rate_reduction * points)
            rate = max(rate, 0.02)
            monthly_rate = rate / 12

            payment = npf.pmt(monthly_rate, months, -loan_amount)
            pmi = (loan_amount * pmi_rate) / 12 if (loan_amount / home_price) > 0.80 else 0
            total_monthly = payment + pmi

            if total_monthly <= max_monthly:
                best_config = {
                    "down_payment": dp,
                    "loan_amount": loan_amount,
                    "rate": rate,
                    "monthly_payment": payment,
                    "pmi": pmi,
                    "points": points,
                    "extra_costs": point_cost
                }
                break

        if best_config:
            break

    return best_config

if not manual_override:
    # --- Loan A ---
    base_rate_a = current_market_rate if current_market_rate else 0.065
    
    loan_a_config = find_best_loan_a(
        home_price=home_price,
        max_down_pct=max_down_pct,
        total_cash=total_cash,
        max_monthly=max_monthly,
        pmi_rate=pmi_rate,
        base_rate=base_rate_a,
        term_years=term_years
    )

    if loan_a_config is not None:
        down_payment_a = loan_a_config["down_payment"]
        loan_amount_a = loan_a_config["loan_amount"]
        rate_a = loan_a_config["rate"]
        monthly_payment_a = loan_a_config["monthly_payment"]
        discount_points_a = loan_a_config["points"]
        extra_costs_a = loan_a_config["extra_costs"]
    
        loan_a_valid = valid_loan(
            loan_amount=loan_amount_a,
            monthly_payment=monthly_payment_a,
            max_monthly=max_monthly,
            total_cash=total_cash,
            down_payment=down_payment_a,
            home_price=home_price,
            pmi_rate=pmi_rate
        )
    else:
        loan_a_valid = False

    # --- Loan B ---
    try:
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
        
        loan_b_valid = valid_loan(
            loan_amount=loan_amount_b,
            monthly_payment=monthly_payment_b,
            max_monthly=max_monthly,
            total_cash=total_cash,
            down_payment=down_payment_b,
            home_price=home_price,
            pmi_rate=pmi_rate
        )
    except:
        st.error("Error calculating Loan B parameters")
        loan_b_valid = False
        discount_rate_b = None
        loan_amount_b = None

else:
    # Manual input section
    st.sidebar.header("Manual Loan A")
    down_payment_a = st.sidebar.number_input("Down Payment A ($)", min_value=0)
    rate_a = st.sidebar.number_input("Interest Rate A (%)", min_value=0.0, max_value=20.0, step=0.01) / 100
    loan_amount_a = home_price - down_payment_a if home_price else None
    monthly_payment_a = npf.pmt(rate_a / 12, months, -loan_amount_a) if loan_amount_a else None
    discount_points_a = 0
    extra_costs_a = 0

    loan_a_valid = valid_loan(
        loan_amount=loan_amount_a,
        monthly_payment=monthly_payment_a,
        max_monthly=max_monthly,
        total_cash=total_cash,
        down_payment=down_payment_a,
        home_price=home_price,
        pmi_rate=pmi_rate
    ) if loan_amount_a and monthly_payment_a else False

    st.sidebar.header("Manual Loan B")
    down_payment_b = st.sidebar.number_input("Down Payment B ($)", min_value=0)
    rate_b = st.sidebar.number_input("Interest Rate B (%)", min_value=0.0, max_value=20.0, step=0.01) / 100
    loan_amount_b = home_price - down_payment_b if home_price else None
    discount_points_b = st.sidebar.number_input("Discount Points B", min_value=0)
    extra_costs_b = loan_amount_b * (discount_points_b * 0.01) if loan_amount_b else 0
    monthly_payment_b = npf.pmt(rate_b / 12, months, -loan_amount_b) if loan_amount_b else None

    loan_b_valid = valid_loan(
        loan_amount=loan_amount_b,
        monthly_payment=monthly_payment_b,
        max_monthly=max_monthly,
        total_cash=total_cash,
        down_payment=down_payment_b,
        home_price=home_price,
        pmi_rate=pmi_rate
    ) if loan_amount_b and monthly_payment_b else False
    discount_rate_b = rate_b  # Set for manual input case

# -------------------------------
# Validation and Calculation
# -------------------------------
if not home_price or not total_cash or not current_market_rate or not max_down_pct or not max_monthly or not pmi_rate:
    st.warning("⚠️ Please fill in all input fields to proceed.")
    st.stop()

if not loan_a_valid or not loan_b_valid:
    st.error("⚠️ No scenario found for one or both loans with the current inputs. Please adjust your loan parameters.")
    st.stop()

try:
    loan_a_df = amortization_schedule(loan_amount=loan_amount_a, annual_rate=rate_a, term_years=term_years, home_price=home_price, pmi_rate=pmi_rate, extra_costs=extra_costs_a)
    loan_b_df = amortization_schedule(loan_amount=loan_amount_b, annual_rate=discount_rate_b, term_years=term_years, home_price=home_price, pmi_rate=pmi_rate, extra_costs=extra_costs_b)
except Exception as e:
    st.error(f"Error generating amortization schedules: {str(e)}")
    st.stop()

def count_pmi_months(df):
    return (df["PMI"] > 0).sum()

# Generate Summary Data
def get_summary_points(df, years=[1, 2, 3, 4, 5, 10, 15, 20, 25, 30]):
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
summary_final.drop(columns=["Total Payment", "Total Interest", "Remaining Balance"], inplace=True)
summary_final["Loan A: Total Payment"] = summary_a["Total Payment"]
summary_final["Loan A: Interest"] = summary_a["Total Interest"]
summary_final["Loan A: Balance"] = summary_a["Remaining Balance"]
summary_final["Loan B: Total Payment"] = summary_b["Total Payment"]
summary_final["Loan B: Interest"] = summary_b["Total Interest"]
summary_final["Loan B: Balance"] = summary_b["Remaining Balance"]

def format_currency(df):
    currency_cols = [col for col in df.columns if "Payment" in col or "Interest" in col or "Balance" in col]
    for col in currency_cols:
        df[col] = df[col].apply(lambda x: f"${x:,.0f}")
    return df

summary_display = format_currency(summary_final.copy())

# Display Results
st.header("📋 Loan Comparison Summary")

if not home_price or not loan_amount_a or not loan_amount_b:
    st.error("⚠️ Critical values missing. Please restart the app.")
    st.stop()

def display_loan_details(title, home_price, down_payment, rate, discount_points, closing_cost, pmi_rate, pmi_start, monthly_payment, df):
    st.subheader(title)
    dp_pct = down_payment / home_price * 100 if home_price else 0
    pmi_months = count_pmi_months(df)
    total_monthly = monthly_payment + pmi_start if pmi_start else monthly_payment

    st.markdown(f"- **Home Price**: ${home_price:,.0f}")
    st.markdown(f"- **Down Payment**: ${down_payment:,.0f} ({dp_pct:.2f}%)")
    st.markdown(f"- **Loan Amount**: ${home_price - down_payment:,.0f}")
    st.markdown(f"- **Interest Rate**: {rate * 100:.2f}%")
    st.markdown(f"- **Discount Points**: {discount_points}")
    st.markdown(f"- **Closing Cost**: ${closing_cost:,.2f}")
    st.markdown(f"- **PMI Rate**: {pmi_rate * 100:.2f}%")
    if pmi_start:
        st.markdown(f"- **PMI (Monthly \\$ Estimate)**: ${pmi_start:,.2f}")
    else:
        st.markdown("- **PMI (Monthly \\$ Estimate)**: $0.00")
    st.markdown(f"- **Total Number of PMI Months**: {pmi_months}")
    st.markdown(f"- **P&I Monthly Payment**: ${monthly_payment:,.2f}")
    st.markdown(f"- **Total Monthly Payment**: ${total_monthly:,.2f}")

col1, col2 = st.columns(2)

with col1:
    pmi_a_start = (loan_amount_a * pmi_rate / 12) if loan_amount_a and (loan_amount_a / home_price) > 0.80 else 0
    display_loan_details("Loan A", home_price, down_payment_a, rate_a, discount_points_a, extra_costs_a, pmi_rate, pmi_a_start, monthly_payment_a, loan_a_df)

with col2:
    pmi_b_start = (loan_amount_b * pmi_rate / 12) if loan_amount_b and (loan_amount_b / home_price) > 0.80 else 0
    display_loan_details("Loan B", home_price, down_payment_b, discount_rate_b, discount_points_b, extra_costs_b, pmi_rate, pmi_b_start, monthly_payment_b, loan_b_df)

st.subheader("📊 Loan Performance Over Time")
st.dataframe(summary_final.set_index("Year"))
