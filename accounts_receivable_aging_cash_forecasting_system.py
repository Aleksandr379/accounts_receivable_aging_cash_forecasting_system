import streamlit as st
import pandas as pd
import openpyxl
import re
from datetime import date

st.title("Accounts Receivable Aging & Cash Forecasting System")
st.info(
    "When you upload your Excel file, please make sure your column names are exactly:\n\n"
    "- Customer Name\n"
    "- Invoice Number\n"
    "- Invoice Date\n"
    "- Due Date\n"
    "- Amount\n"
    "- Payment Date\n"
    "- Payment Amount\n"
)

# -----------------------------
# 1️⃣ Input Mode Selection
# -----------------------------
mode = st.radio(
    "How do you like to input invoices?",
    ("Upload CSV/Excel", "Enter Manually")
)

uploaded_file = None

# -----------------------------
# 2️⃣ Upload CSV/Excel
# -----------------------------

if mode == "Upload CSV/Excel":
    st.subheader("Upload your file")
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])

    if uploaded_file is not None:
        st.success("File uploaded successfully!")

        # -----------------------------
        # Read the file
        # -----------------------------
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # -----------------------------
        # Normalize column headers
        # -----------------------------
        def clean_column(col_name):
            col_name = col_name.strip().lower()              # remove spaces and lowercase
            col_name = re.sub(r'[^a-z0-9 ]', '', col_name)  # remove special characters
            col_name = re.sub(r'\s+', ' ', col_name)        # collapse multiple spaces
            return col_name

        df.columns = [clean_column(c) for c in df.columns]

        # -----------------------------
        # Map alternatives to required columns
        # -----------------------------
        column_map = {
            'vendor name': 'Customer Name',
            'cust name': 'Customer Name',
            'client name': 'Customer Name',
            'customer': 'Customer Name',
            'invoice no': 'Invoice Number',
            'inv no': 'Invoice Number',
            'invoice number': 'Invoice Number',
            'date of invoice': 'Invoice Date',
            'inv date': 'Invoice Date',
            'billing date': 'Invoice Date',
            'date': 'Invoice Date',
            'due date': 'Due Date',
            'payment due date': 'Due Date',
            'amount': 'Amount',
            'invoice amount': 'Amount',
            'total': 'Amount',
            'paid date': 'Payment Date',
            'date paid': 'Payment Date',
            'payment received': 'Payment Date',
            'paid amount': 'Payment Amount',
            'amount paid': 'Payment Amount',
        }

        # Normalize mapping keys same way as df.columns
        column_map_clean = {clean_column(k): v for k, v in column_map.items()}

        # Rename columns if alternative exists
        for alt_name, correct_name in column_map_clean.items():
            if alt_name in df.columns:
                df.rename(columns={alt_name: correct_name}, inplace=True)

        # -----------------------------
        # Validate required columns
        # -----------------------------
        required_cols = ['Customer Name', 'Invoice Number', 'Invoice Date', 'Due Date', 'Amount', 'Payment Date', 'Payment Amount']
        missing_cols = [c for c in required_cols if c not in df.columns]

        if missing_cols:
            st.error(f"Uploaded file is missing required columns: {missing_cols}")
            st.stop()

        # -----------------------------
        # Display uploaded dataframe
        # -----------------------------
        st.dataframe(df.head())

# -----------------------------
# 3️⃣ Manual Entry
# -----------------------------
elif mode == "Enter Manually":
    st.subheader("Enter details manually")
    with st.form(key="manual_form"):
        customer_name = st.text_input("Customer Name")
        invoice_number = st.text_input("Invoice Number")
        invoice_date = st.date_input("Invoice Date")
        due_date = st.date_input("Due Date")
        amount = st.number_input("Amount", min_value=0.0, step=0.01)
        has_payment = st.checkbox("Has Payment Been Made?")
        payment_date = st.date_input("Payment Date", value=date.today()) if has_payment else None
        payment_amount = st.number_input("Payment Amount", min_value=0.0, step=0.01) if has_payment else 0.0

        submit_button = st.form_submit_button(label="Add Invoice Data")

        if "manual_invoices" not in st.session_state:
            st.session_state.manual_invoices = []

        if submit_button:
            if not customer_name or not invoice_number:
                st.error("Customer Name and Invoice Number are required.")
            elif due_date < invoice_date:
                st.error("Due Date cannot be before Invoice Date.")
            else:
                st.session_state.manual_invoices.append({
                    "Customer Name": customer_name,
                    "Invoice Number": invoice_number,
                    "Invoice Date": invoice_date,
                    "Due Date": due_date,
                    "Amount": amount,
                    "Payment Date": payment_date,
                    "Payment Amount": payment_amount
                })
                st.success(f"Invoice {invoice_number} for {customer_name} added!")
                st.rerun()

# -----------------------------
# 4️⃣ Combine Uploaded + Manual Data
# -----------------------------
ar_df = None

if uploaded_file is not None:
    ar_df = df.copy()

if "manual_invoices" in st.session_state and st.session_state.manual_invoices:
    manual_df = pd.DataFrame(st.session_state.manual_invoices)
    ar_df = pd.concat([ar_df, manual_df], ignore_index=True) if ar_df is not None else manual_df

# -----------------------------
# 5️⃣ Process AR Aging & Cash Forecast
# -----------------------------
if ar_df is not None and not ar_df.empty:
    # Validate required columns
    required_cols = ['Customer Name', 'Invoice Number', 'Invoice Date', 'Due Date', 'Amount', 'Payment Date']
    missing_cols = [c for c in required_cols if c not in ar_df.columns]
    if missing_cols:
        st.error(f"Uploaded file is missing required columns: {missing_cols}")
        st.stop()

    # -----------------------------
    # Status Filter
    # -----------------------------
    status_filter = st.radio(
        "Invoice Status",
        ["All", "Unpaid Only", "Paid Only"],
        horizontal=True
    )

    # Ensure correct types
    ar_df['Invoice Date'] = pd.to_datetime(ar_df['Invoice Date'], errors='coerce')
    ar_df['Due Date'] = pd.to_datetime(ar_df['Due Date'], errors='coerce')
    ar_df['Payment Date'] = pd.to_datetime(ar_df['Payment Date'], errors='coerce')
    if 'Payment Amount' not in ar_df.columns:
        ar_df['Payment Amount'] = 0.0
    else:
        ar_df['Payment Amount'] = ar_df['Payment Amount'].fillna(0)


    # Calculate outstanding amount
    ar_df['Outstanding Amount'] = (ar_df['Amount'] - ar_df['Payment Amount']).clip(lower=0)
    ar_df['Payment Status'] = ar_df['Outstanding Amount'].apply(lambda x: "Paid" if x == 0 else "Unpaid")

    # Apply status filter
    filtered_df = ar_df.copy()
    if status_filter == "Unpaid Only":
        filtered_df = filtered_df[filtered_df['Payment Status'] == "Unpaid"]
    elif status_filter == "Paid Only":
        filtered_df = filtered_df[filtered_df['Payment Status'] == "Paid"]

    # -----------------------------
    # AR Aging
    # -----------------------------
    today = pd.to_datetime(date.today())
    filtered_df['Days Outstanding'] = (today - filtered_df['Due Date']).dt.days
    filtered_df.loc[filtered_df['Days Outstanding'] < 0, 'Days Outstanding'] = 0

    def aging_category(days):
        if days <= 30:
            return "0-30"
        elif days <= 60:
            return "31-60"
        elif days <= 90:
            return "61-90"
        else:
            return ">90"

    filtered_df['Aging Category'] = filtered_df['Days Outstanding'].apply(aging_category)
    aging_summary = filtered_df.groupby('Aging Category')['Outstanding Amount'].sum().reindex(
        ["0-30", "31-60", "61-90", ">90"], fill_value=0
    ).reset_index()

    st.subheader("Accounts Receivable Aging")
    st.dataframe(aging_summary)
    st.bar_chart(aging_summary.set_index('Aging Category'))

    # -----------------------------
    # Cash Forecast
    # -----------------------------
    bucket = st.selectbox("Cash Forecast Bucket", ["Daily", "Weekly", "Monthly"])
    cash_option = st.radio("Cash Forecast Invoices", ["Unpaid Only", "Paid Only", "Both Paid and Unpaid"], horizontal=True)

    def create_cash_df(df, cash_option):
        df = df.copy()
        if cash_option == "Unpaid Only":
            df = df[df['Outstanding Amount'] > 0].copy()
            df['Expected Payment'] = df['Due Date']
            df['Cash Amount'] = df['Outstanding Amount']
        elif cash_option == "Paid Only":
            df = df[df['Outstanding Amount'] == 0].copy()
            df['Expected Payment'] = df['Payment Date']
            df['Cash Amount'] = df['Payment Amount']
        else:  # Both
            df['Expected Payment'] = df['Payment Date'].fillna(df['Due Date'])
    
            # Vectorized version for better performance
            df['Cash Amount'] = df['Outstanding Amount']
            df.loc[df['Outstanding Amount'] == 0, 'Cash Amount'] = df['Payment Amount']

        df['Expected Payment'] = pd.to_datetime(df['Expected Payment'])
        return df

    cash_df = create_cash_df(filtered_df, cash_option)
    if cash_df.empty:
        st.warning("No invoices available for selected cash forecast options.")
        st.stop()

    if bucket == "Weekly":
        cash_df['Bucket Date'] = cash_df['Expected Payment'].dt.to_period('W').dt.start_time
    elif bucket == "Monthly":
        cash_df['Bucket Date'] = cash_df['Expected Payment'].dt.to_period('M').dt.start_time
    else:
        cash_df['Bucket Date'] = cash_df['Expected Payment']

    cash_forecast = (
        cash_df
        .groupby('Bucket Date')['Cash Amount']
        .sum()
        .reset_index()
        .sort_values('Bucket Date')
    )

    st.subheader("Overall Cash Forecast")
    st.dataframe(cash_forecast)
    st.line_chart(cash_forecast.set_index('Bucket Date'))

    # -----------------------------
    # Customer-specific AR & Cash
    # -----------------------------
    customers = filtered_df['Customer Name'].dropna().unique()
    if len(customers) > 0:
        selected_customer = st.selectbox("Filter by Customer", customers)
        customer_df = filtered_df[filtered_df['Customer Name'] == selected_customer].copy()

        customer_aging = customer_df.groupby('Aging Category')['Outstanding Amount'].sum().reindex(
            ["0-30", "31-60", "61-90", ">90"], fill_value=0
        ).reset_index()
        st.subheader(f"{selected_customer} - Accounts Receivable Aging")
        st.dataframe(customer_aging)
        st.bar_chart(customer_aging.set_index('Aging Category'))

        customer_cash_df = create_cash_df(customer_df, cash_option)

        if not customer_cash_df.empty:
            if bucket == "Weekly":
                customer_cash_df['Bucket Date'] = customer_cash_df['Expected Payment'].dt.to_period('W').dt.start_time
            elif bucket == "Monthly":
                customer_cash_df['Bucket Date'] = customer_cash_df['Expected Payment'].dt.to_period('M').dt.start_time
            else:
                customer_cash_df['Bucket Date'] = customer_cash_df['Expected Payment']

            customer_cf = (
                customer_cash_df.groupby('Bucket Date')['Cash Amount']
                .sum()
                .reset_index()
                .sort_values('Bucket Date')
            )
            st.subheader(f"{selected_customer} - Cash Forecast")
            st.dataframe(customer_cf)
            st.line_chart(customer_cf.set_index('Bucket Date'))
        else:
            st.info("No cash forecast data for this customer.")

    # -----------------------------
    # Summary Metrics
    # -----------------------------
    st.subheader("Summary Metrics")
    st.metric("Total Accounts Receivable", f"${filtered_df['Outstanding Amount'].sum():,.2f}")
    st.metric("Total Expected Cash", f"${cash_forecast['Cash Amount'].sum():,.2f}")

    # -----------------------------
    # Download Reports
    # -----------------------------
    st.subheader("Download Reports")
    st.download_button("Download Full Invoices CSV", data=ar_df.to_csv(index=False), file_name="full_invoices.csv", mime="text/csv")
    st.download_button("Download AR Aging Summary CSV", data=aging_summary.to_csv(index=False), file_name="ar_aging_summary.csv", mime="text/csv")
    st.download_button("Download Cash Forecast CSV", data=cash_forecast.to_csv(index=False), file_name="cash_forecast.csv", mime="text/csv")
