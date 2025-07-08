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
    # Ensure home_price is not zero to avoid division by zero
    if home_price <= 0:
        return False
    pmi = (loan_amount * pmi_rate) / 12 if (loan_amount / home_price) > 0.80 else 0
    total_monthly = monthly_payment + pmi
    if total_monthly > max_monthly or total_monthly <= 0:
        return False
    # Ensure down_payment doesn't exceed total_cash or is negative (already handled by max(0, down_payment))
    # if down_payment > total_cash:
    #     return False
    return True

# -------------------------------
# Loan Schedule with PMI logic
# -------------------------------
def amortization_schedule(loan_amount, annual_rate, term_years, home_price, start_year=0, pmi_rate=0, extra_costs=0):
    monthly_rate = annual_rate / 12
    months = term_years * 12
    
    # Handle cases where loan_amount or monthly_rate might be problematic
    if loan_amount <= 0 or monthly_rate <= 0: # Check for non-positive values
        # If rate is 0, principal repayment is just loan_amount / months
        if monthly_rate == 0:
            payment = loan_amount / months
        else:
            return pd.DataFrame() # Return empty if loan_amount is 0 and rate isn't 0
    else:
        try:
            payment = npf.pmt(monthly_rate, months, -loan_amount)
        except ZeroDivisionError: # Catch case if months is 0, though unlikely with term_years=30
            return pd.DataFrame()

    schedule = []
    balance = loan_amount
    total_interest = 0
    max_ltv = 0.80

    for m in range(1, months + 1):
        interest = balance * monthly_rate
        principal = payment - interest
        balance -= principal
        total_interest += interest

        # Ensure home_price is not zero before division
        current_ltv = balance / home_price if home_price > 0 else 0 
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
    if not (home_price and max_down_pct is not None and total_cash is not None and max_monthly is not None):
        return None
        
    months = term_years * 12
    max_down_payment = min(home_price * max_down_pct / 100, total_cash)
    min_down_payment = home_price * 0.03 # Assuming a minimum down payment, e.g., 3% for search
    
    # Ensure min_down_payment is not greater than max_down_payment if home_price is small
    if min_down_payment > max_down_payment:
        # If minimum down payment exceeds max available cash or max_down_pct,
        # adjust min_down_payment to allow search range
        min_down_payment = max_down_payment # Or handle this as an invalid scenario earlier
        if min_down_payment < 0: min_down_payment = 0 # Ensure it's not negative

    step = 1000

    best_config = None

    # Iterate down payments from max allowed down to min allowed down (or 0)
    # Using range(start, stop, step) - stop is exclusive, so -1 to include min_down_payment if step is 1
    # Or, adjust to ensure search includes relevant low down payments.
    for dp in range(int(max_down_payment), int(min_down_payment) -1 , -step):
        if dp < 0: # Ensure down payment doesn't go negative during iteration
            dp = 0
        
        loan_amount = home_price - dp
        
        # Ensure loan_amount is positive before calculating point_cost
        if loan_amount <= 0:
            continue # Skip if loan_amount is invalid

        available_cash_for_points = total_cash - dp
        if available_cash_for_points < 0:
            available_cash_for_points = 0 # Cannot use negative cash for points

        for points in range(0, max_points_allowed + 1):
            point_cost = loan_amount * (points * 0.01)
            if point_cost > available_cash_for_points:
                continue # Cannot afford these points

            rate = base_rate - (point_rate_reduction * points)
            rate = max(rate, 0.02) # Cap minimum rate to 2% (or another reasonable floor)
            monthly_rate = rate / 12

            if monthly_rate <= 0 and loan_amount > 0: # Handle zero or negative interest rate for pmt
                payment = loan_amount / months if months > 0 else 0
            else:
                try:
                    payment = npf.pmt(monthly_rate, months, -loan_amount)
                except Exception: # Catch potential errors from npf.pmt (e.g. very low rate, long term)
                    continue

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
                break # Found a valid config for this down payment, move to next dp
        
        if best_config:
            break # Found a valid config, exit outer loop

    return best_config

# Initialize loan parameters outside the if/else for manual_override to ensure they always exist
down_payment_a = 0
loan_amount_a = 0
rate_a = 0.0
monthly_payment_a = 0
discount_points_a = 0
extra_costs_a = 0
loan_a_valid = False

down_payment_b = 0
loan_amount_b = 0
discount_rate_b = 0.0
monthly_payment_b = 0
discount_points_b = 0
extra_costs_b = 0
loan_b_valid = False


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

    # --- Loan B (MODIFIED LOGIC: Use all Total Cash Available) ---
    try:
        # Step 1: Define a baseline loan amount for calculating the cost of 1 point.
        # This is a common practice to stabilize point cost calculations.
        # Here, we assume a 3% down payment for this *initial* loan amount calculation.
        initial_dp_for_point_calc = home_price * 0.03 
        loan_amount_for_point_calc = home_price - initial_dp_for_point_calc
        
        # Ensure initial loan amount is valid for point calculation
        if loan_amount_for_point_calc <= 0:
            raise ValueError("Loan amount for point calculation is invalid.")

        cost_of_one_point = loan_amount_for_point_calc * 0.01

        # Step 2: Calculate the maximum number of points that can be bought
        # using the majority of the total cash available.
        # This is the cash that will be potentially spent on points.
        # We assume for point calculation, the available cash is total_cash minus a nominal down payment.
        cash_available_for_points = total_cash - initial_dp_for_point_calc
        
        if cash_available_for_points < 0:
            cash_available_for_points = 0

        max_points = int(cash_available_for_points // cost_of_one_point) if cost_of_one_point > 0 else 0
        
        # Cap max_points to a reasonable number to prevent extreme scenarios or very low rates
        max_points = min(max_points, 20) 

        # Step 3: Calculate the actual cost of these discount points
        extra_costs_b = max_points * cost_of_one_point

        # Step 4: The actual down payment is whatever cash is left after paying for the points
        down_payment_b = total_cash - extra_costs_b
        
        # Ensure down_payment_b is not negative. If it is, it means total_cash isn't enough for points+any DP.
        down_payment_b = max(0, down_payment_b) 

        # Step 5: Recalculate the loan amount based on the *actual* down payment
        loan_amount_b = home_price - down_payment_b
        
        # Ensure the final loan amount is positive for further calculations
        if loan_amount_b <= 0:
            raise ValueError("Final Loan B amount is zero or negative after down payment.")

        # Step 6: Calculate the final interest rate after applying discount points
        discount_rate_b = max(current_market_rate - (0.0025 * max_points), 0.02) # Cap rate at 2%
        monthly_rate_b = discount_rate_b / 12

        # Step 7: Calculate the monthly P&I payment
        if monthly_rate_b <= 0 and loan_amount_b > 0:
            monthly_payment_b = loan_amount_b / months if months > 0 else 0
        else:
            monthly_payment_b = npf.pmt(monthly_rate_b, months, -loan_amount_b)

        discount_points_b = max_points # Assign the number of points for display

        # Step 8: Validate the entire Loan B configuration
        loan_b_valid = valid_loan(
            loan_amount=loan_amount_b,
            monthly_payment=monthly_payment_b,
            max_monthly=max_monthly,
            total_cash=total_cash, # Pass original total_cash for validation
            down_payment=down_payment_b, # Pass the *newly calculated* down_payment_b
            home_price=home_price,
            pmi_rate=pmi_rate
        )
    except Exception as e:
        st.error(f"Error calculating Loan B parameters: {str(e)}")
        loan_b_valid = False
        # Reset values to 0 on error to prevent using stale/invalid numbers
        discount_rate_b = 0.0
        loan_amount_b = 0
        down_payment_b = 0
        monthly_payment_b = 0
        discount_points_b = 0
        extra_costs_b = 0

else: # manual_override is True
    # Manual input section for Loan A
    st.sidebar.header("Manual Loan A")
    down_payment_a = st.sidebar.number_input("Down Payment A ($)", min_value=0)
    rate_a = st.sidebar.number_input("Interest Rate A (%)", min_value=0.0, max_value=20.0, step=0.01) / 100
    loan_amount_a = home_price - down_payment_a if home_price else 0
    # Ensure loan_amount_a is positive for pmt calculation
    if loan_amount_a < 0: loan_amount_a = 0 
    
    if rate_a <= 0 and loan_amount_a > 0:
        monthly_payment_a = loan_amount_a / months if months > 0 else 0
    else:
        monthly_payment_a = npf.pmt(rate_a / 12, months, -loan_amount_a) if loan_amount_a else 0
    
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
    ) if (loan_amount_a is not None and monthly_payment_a is not None and home_price > 0) else False # Add home_price check

    # Manual input section for Loan B
    st.sidebar.header("Manual Loan B")
    down_payment_b = st.sidebar.number_input("Down Payment B ($)", min_value=0)
    rate_b = st.sidebar.number_input("Interest Rate B (%)", min_value=0.0, max_value=20.0, step=0.01) / 100
    loan_amount_b = home_price - down_payment_b if home_price else 0
    # Ensure loan_amount_b is positive for pmt calculation
    if loan_amount_b < 0: loan_amount_b = 0

    discount_points_b = st.sidebar.number_input("Discount Points B", min_value=0)
    extra_costs_b = loan_amount_b * (discount_points_b * 0.01) if loan_amount_b else 0
    
    if rate_b <= 0 and loan_amount_b > 0:
        monthly_payment_b = loan_amount_b / months if months > 0 else 0
    else:
        monthly_payment_b = npf.pmt(rate_b / 12, months, -loan_amount_b) if loan_amount_b else 0

    loan_b_valid = valid_loan(
        loan_amount=loan_amount_b,
        monthly_payment=monthly_payment_b,
        max_monthly=max_monthly,
        total_cash=total_cash,
        down_payment=down_payment_b,
        home_price=home_price,
        pmi_rate=pmi_rate
    ) if (loan_amount_b is not None and monthly_payment_b is not None and home_price > 0) else False # Add home_price check
    
    discount_rate_b = rate_b # Set for manual input case

# -------------------------------
# Validation and Conditional Display
# -------------------------------
can_display_results = True # Initialize flag

# Validation 1: Initial Inputs - Ensure fundamental inputs are provided
if not home_price or not total_cash or not current_market_rate or max_down_pct is None or not max_monthly or not pmi_rate:
    st.warning("⚠️ Please fill in all input fields to proceed.")
    can_display_results = False

# Validation 2: Loan A & B validity - Check if scenarios are calculable/valid
if can_display_results: # Only check if previous validations passed
    if not loan_a_valid or not loan_b_valid:
        st.error("⚠️ No viable scenario found for one or both loans with the current inputs. Please adjust your loan parameters.")
        can_display_results = False

# Validation 3: Critical values for display - Ensure no division by zero or None values for core calculations
if can_display_results: # Only check if previous validations passed
    if home_price <= 0 or loan_amount_a is None or loan_amount_a <=0 or loan_amount_b is None or loan_amount_b <=0:
        st.error("⚠️ Critical loan amounts or home price missing or invalid for comparison. Please adjust inputs.")
        can_display_results = False

# Only proceed with calculations and display if all validations pass
if can_display_results:
    try:
        loan_a_df = amortization_schedule(loan_amount=loan_amount_a, annual_rate=rate_a, term_years=term_years, home_price=home_price, pmi_rate=pmi_rate, extra_costs=extra_costs_a)
        loan_b_df = amortization_schedule(loan_amount=loan_amount_b, annual_rate=discount_rate_b, term_years=term_years, home_price=home_price, pmi_rate=pmi_rate, extra_costs=extra_costs_b)
        
        # Check if DataFrames were generated successfully and are not empty
        if loan_a_df.empty or loan_b_df.empty:
            raise ValueError("Amortization schedule generation resulted in empty DataFrames.")

    except Exception as e:
        st.error(f"Error generating amortization schedules: {str(e)}")
        can_display_results = False # Set flag to False if error during schedule generation

# If after all checks, we can display results:
if can_display_results:
    def count_pmi_months(df):
        return (df["PMI"] > 0).sum()

    # Generate Summary Data
    def get_summary_points(df, years=[1, 2, 3, 4, 5, 10, 15, 20, 25, 30]):
        result = []
        for yr in years:
            slice_df = df[df["Year"] < yr*12] # Slice up to the beginning of the target year
            total_payment = slice_df["Total Payment"].sum()
            total_interest = slice_df["Interest"].sum()
            
            # Remaining balance is from the *end* of the target year
            # Find the last balance of the target year, if the year exists in the dataframe
            remaining_balance = df[df["Year"] == yr].iloc[-1]["Balance"] if not df[df["Year"] == yr].empty else (df.iloc[-1]["Balance"] if not df.empty else 0)
            
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

    def display_loan_details(title, home_price, down_payment, rate, discount_points, closing_cost, pmi_rate, pmi_start, monthly_payment, df):
        st.subheader(title)
        dp_pct = down_payment / home_price * 100 if home_price > 0 else 0 # Ensure home_price > 0
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
        pmi_a_start = (loan_amount_a * pmi_rate / 12) if loan_amount_a and home_price and (loan_amount_a / home_price) > 0.80 else 0
        display_loan_details("Loan A", home_price, down_payment_a, rate_a, discount_points_a, extra_costs_a, pmi_rate, pmi_a_start, monthly_payment_a, loan_a_df)

    with col2:
        pmi_b_start = (loan_amount_b * pmi_rate / 12) if loan_amount_b and home_price and (loan_amount_b / home_price) > 0.80 else 0
        display_loan_details("Loan B", home_price, down_payment_b, discount_rate_b, discount_points_b, extra_costs_b, pmi_rate, pmi_b_start, monthly_payment_b, loan_b_df)

    st.subheader("📊 Loan Performance Over Time")
    st.dataframe(summary_final.set_index("Year"))

# --- Footer --- (This is outside the 'if can_display_results' block, so it always shows)
st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 14px;">
    <p>✨ Crafted with care by <strong>Zeel Vachhani</strong> ✨</p>
    <p>© 2025 Zeel Vachhani. All rights reserved.</p>
    <p><em>This tool is for informational purposes only and should not be considered financial advice.</em></p>
</div>
""", unsafe_allow_html=True)
