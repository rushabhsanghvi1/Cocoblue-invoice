import streamlit as st
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
import re
import textwrap
from datetime import datetime
import io

# --- CONFIGURATION ---
DEFAULT_BILL_FROM = """KAMALA-E-RETAIL,
34-C, Shreeji Estate Vasta Devdi Road,
SURAT GUJARAT - 395004
GSTIN: 24ABAFK8424H1ZG"""

DEFAULT_BILL_TO = """COCOBLU RETAIL LIMITED,
71, Brahmin Mitra Mandal Society,
Opp. Jalram Temple, Ellisbridge, AHMEDABAD, GUJARAT - 380006
GSTIN: 24AAJCC8517E1ZR"""

DEFAULT_AUTH_SIGNATORY = "Authorized Signatory"
DEFAULT_CREDITS = "Prepared By: Jain Sanghvi & Co."
SIGNATURE_FONT_FILE = "DancingScript-Regular.ttf"
LOGO_FILE = "logo.png"

# --- Helper Functions (Copied from original script) ---

def merge_address(order_row):
    """Merge address fields from order data"""
    cols = [
        'Ship To Address Line 1',
        'Ship To Address Line 2',
        'Ship To Address Line 3',
        'Ship To City',
        'Ship To State',
        'Ship To ZIP Code',
    ]
    address_parts = []
    for col in cols:
        val = str(order_row.get(col, ''))
        if val and val != 'nan' and val.strip():
            address_parts.append(val.strip())
    return ', '.join(address_parts)

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    filename = filename.replace('/', '_').replace('\\', '_')
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    return filename

def format_date_only(date_str):
    """Extract only date from datetime string (remove time)"""
    try:
        date_obj = pd.to_datetime(date_str)
        return date_obj.strftime('%d-%m-%Y')
    except (ValueError, TypeError):
        return str(date_str).split(' ')[0]

def clean_currency(value):
    """Clean currency value - remove rupee symbol, commas, and convert to float"""
    try:
        val_str = str(value).strip()
        val_str = val_str.replace('₹', '').replace('Rs.', '').replace('Rs', '')
        val_str = val_str.replace(',', '').strip()
        return float(val_str)
    except ValueError:
        print(f"Warning: Could not convert '{value}' to float")
        return 0.0

def number_to_words(n):
    """Converts a float number (like currency) to Indian numbering system words."""
    try:
        n = float(n)
        rupees = int(n)
        paise = int(round((n - rupees) * 100))

        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
        teens = ["", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def convert_to_words(num):
            if num == 0: return ""
            if num < 10: return units[num]
            if num == 10: return tens[1]
            if num < 20: return teens[num - 10]
            if num < 100: return tens[num // 10] + " " + units[num % 10]
            if num < 1000: return units[num // 100] + " Hundred " + convert_to_words(num % 100)
            if num < 100000: return convert_to_words(num // 1000) + " Thousand " + convert_to_words(num % 1000)
            if num < 10000000: return convert_to_words(num // 100000) + " Lakh " + convert_to_words(num % 100000)
            return convert_to_words(num // 10000000) + " Crore " + convert_to_words(num % 10000000)

        rupees_words = convert_to_words(rupees).strip()
        paise_words = convert_to_words(paise).strip()

        result = ""
        if rupees_words:
            result = f"Rupees {rupees_words.strip()}"
        else:
            result = "Rupees Zero"

        if paise_words:
            result += f" and {paise_words.strip()} Paise"
        
        return result.replace("  ", " ") + " Only"

    except Exception as e:
        print(f"Error converting number to words: {e}")
        return "Error"


# --- Professional PDF Class (Copied from original script) ---

class PDFInvoice(FPDF):
    def __init__(self, bill_from, bill_to, company_name):
        super().__init__()
        self.is_annexure_page = False
        self.bill_from = bill_from
        self.bill_to = bill_to
        self.company_name = company_name
        self.logo_path = LOGO_FILE
        
        # --- Add Signature Font ---
        self.signature_font_available = False
        try:
            if os.path.exists(SIGNATURE_FONT_FILE):
                # Added uni=True to properly process the TTF font
                self.add_font('DancingScript', '', SIGNATURE_FONT_FILE, uni=True) 
                self.signature_font_available = True
            else:
                 print(f"Warning: Signature font '{SIGNATURE_FONT_FILE}' not found. Skipping.")
        except Exception as e:
            # CATCH THE ERROR GRACEFULLY
            print(f"CRITICAL: Failed to load signature font '{SIGNATURE_FONT_FILE}'.")
            print(f"Error: {e}")
            print("The PDF will generate, but without the cursive signature.")
            self.signature_font_available = False

    def header(self):
        if self.is_annexure_page:
            return

        # --- Logo ---
        logo_w = 0
        try:
            if os.path.exists(self.logo_path):
                self.image(self.logo_path, x=10, y=8, w=30) # Smaller logo
                logo_w = 35 # Space taken by logo
        except Exception as e:
            print(f"Warning: Could not load logo. {e}")
        
        # --- Firm Name (Header) ---
        self.set_y(12)
        self.set_x(10 + logo_w)
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(60, 110, 180) # Professional Blue
        self.cell(0, 10, self.company_name, border=0, align='L')
        
        # --- Invoice Title ---
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(0, 0, 0) # Reset color
        self.set_y(15)
        self.cell(0, 10, 'TAX INVOICE', align='R')
        self.ln(15)

        # --- Bill From / Bill To ---
        self.set_font('Helvetica', 'B', 10)
        y_start = self.get_y()
        
        self.set_x(10)
        self.cell(95, 5, 'Bill From:', new_x=XPos.LMARGIN, new_y=YPos.NEXT, border=0)
        self.set_font('Helvetica', '', 9)
        self.multi_cell(95, 4, self.bill_from, align='L', border=0)
        
        self.set_y(y_start)
        self.set_x(105)
        self.set_font('Helvetica', 'B', 10)
        self.cell(95, 5, 'Bill To:', new_x=XPos.LMARGIN, new_y=YPos.NEXT, border=0)
        self.set_x(105)
        self.set_font('Helvetica', '', 9)
        self.multi_cell(95, 4, self.bill_to, align='L', border=0)
        
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

    def draw_invoice_table_header(self, col_widths, col_names):
        self.set_font("Helvetica", 'B', 9)
        self.set_fill_color(230, 230, 230)
        for i, col in enumerate(col_names):
            align = 'R' if col in ['Sr.', 'Qty', 'Rate', 'Amount', 'CGST', 'SGST', 'Total'] else 'C'
            if col == 'ASIN':
                align = 'L'
            self.cell(col_widths[i], 7, col, border=1, align=align, fill=True)
        self.ln()
    
    def draw_invoice_table_row(self, col_widths, vals):
        self.set_font("Helvetica", '', 8)
        for i, val in enumerate(vals):
            # Sr, Qty, Rate, Amount, CGST, SGST, Total are right-aligned
            align = 'R' if i in [0, 3, 4, 5, 7, 8, 9] else 'L'
            # HSN, GST% are centered
            if i in [2, 6]: 
                align = 'C'
            # ASIN is left-aligned (index 1)
            self.cell(col_widths[i], 6, str(val), border=1, align=align)
        self.ln()

    def draw_totals_summary(self, total_amount, total_cgst, total_sgst, grand_total):
        self.ln(2)
        summary_label_width = 35
        summary_value_width = 25
        summary_x_pos = self.w - summary_label_width - summary_value_width - self.r_margin

        self.set_font("Helvetica", '', 10)
        
        # Subtotal
        self.set_x(summary_x_pos)
        self.cell(summary_label_width, 6, "Subtotal", border=1, align='L')
        self.cell(summary_value_width, 6, f"{total_amount:.2f}", border=1, align='R')
        self.ln()

        # CGST
        self.set_x(summary_x_pos)
        self.cell(summary_label_width, 6, "Total CGST", border=1, align='L')
        self.cell(summary_value_width, 6, f"{total_cgst:.2f}", border=1, align='R')
        self.ln()
        
        # SGST
        self.set_x(summary_x_pos)
        self.cell(summary_label_width, 6, "Total SGST", border=1, align='L')
        self.cell(summary_value_width, 6, f"{total_sgst:.2f}", border=1, align='R')
        self.ln()

        # Grand Total
        self.set_font("Helvetica", 'B', 11)
        self.set_fill_color(230, 230, 230)
        self.set_x(summary_x_pos)
        self.cell(summary_label_width, 8, "Grand Total (Rs.)", border=1, align='L', fill=True)
        self.cell(summary_value_width, 8, f"{grand_total:.2f}", border=1, align='R', fill=True)
        self.ln(10)
    
    def draw_final_remarks(self, grand_total_words, auth_sig_name):
        """Draws "Amount in Words" and "Signature" sections."""
        
        final_y_start = self.get_y()
        
        # --- Amount in Words (Left Side) ---
        self.set_font("Helvetica", 'B', 9)
        self.cell(100, 5, "Amount in Words:", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", '', 9)
        self.multi_cell(120, 5, grand_total_words, border=0, align='L')
                
        # --- Signature (Right Side) ---
        self.set_y(final_y_start) # Reset Y to align with top of this block
        self.set_font("Helvetica", '', 9)
        
        # Check if we are near the bottom
        if self.get_y() > 240:
             self.add_page()
             self.set_y(final_y_start)
             
        # Text 1: "For [Company Name]"
        self.cell(0, 5, f'For {self.company_name}', align='R')
        self.ln(10) # More space for signature

        # --- Signature (Middle) ---
        if self.signature_font_available:
            self.set_font('DancingScript', '', 16)
            self.cell(0, 8, auth_sig_name, align='R')
            self.ln(5)
        else:
            # If no font, just leave a gap
            self.ln(10)
        # --- End Signature ---

        self.set_font("Helvetica", 'B', 9) # Reset font
        # Text 2: "(Authorized Signatory)"
        self.cell(0, 5, f'({auth_sig_name})', align='R') # Print typed name in brackets

# --- Streamlit UI ---

# Page config
st.set_page_config(page_title="GST Invoice Generator", layout="centered", page_icon="📄")

# Initialize session state
if 'invoice_df' not in st.session_state:
    st.session_state.invoice_df = None
if 'orders_df' not in st.session_state:
    st.session_state.orders_df = None
if 'invoice_ids' not in st.session_state:
    st.session_state.invoice_ids = ["---"]
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'pdf_filename' not in st.session_state:
    st.session_state.pdf_filename = ""

# --- Sidebar for Uploads and Selection ---
with st.sidebar:
    st.header("1. Upload Files")
    
    invoice_file = st.file_uploader("Upload Invoice CSV", type="csv")
    if invoice_file:
        try:
            st.session_state.invoice_df = pd.read_csv(invoice_file)
            st.session_state.invoice_ids = st.session_state.invoice_df['Invoice ID'].unique().tolist()
            st.success("Invoice CSV loaded! ✓")
        except Exception as e:
            st.error(f"Failed to load Invoice CSV: {e}")
            st.session_state.invoice_df = None
            st.session_state.invoice_ids = ["---"]

    orders_file = st.file_uploader("Upload Order CSV", type="csv")
    if orders_file:
        try:
            st.session_state.orders_df = pd.read_csv(orders_file)
            st.success("Order CSV loaded! ✓")
        except Exception as e:
            st.error(f"Failed to load Order CSV: {e}")
            st.session_state.orders_df = None
    
    st.divider()
    st.header("2. Select Invoice")
    
    selected_invoice_id = st.selectbox(
        "Select Invoice ID:",
        options=st.session_state.invoice_ids,
        index=0
    )

# --- Main Page for Configuration ---
st.title("GST Invoice & Annexure Generator")
st.markdown("Configure the invoice details below and use the sidebar to upload files and generate the PDF.")

with st.expander("Edit Invoice Details", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        bill_from_data = st.text_area("Bill From:", value=DEFAULT_BILL_FROM, height=150)
    with col2:
        bill_to_data = st.text_area("Bill To:", value=DEFAULT_BILL_TO, height=150)
    
    auth_sig_name = st.text_input("Authorized Signatory Name:", value=DEFAULT_AUTH_SIGNATORY)

st.divider()

# --- PDF Generation and Download ---
if st.button("🔄 Generate Merged PDF", type="primary", use_container_width=True):
    st.session_state.pdf_bytes = None # Clear previous PDF
    
    # --- Error Checking ---
    if st.session_state.invoice_df is None or st.session_state.orders_df is None:
        st.error("Error: Please upload both Invoice and Order CSV files.")
    elif selected_invoice_id == "---" or not selected_invoice_id:
        st.error("Error: Please select a valid Invoice ID.")
    elif not bill_from_data or not bill_to_data or not auth_sig_name:
        st.error("Error: Please fill in 'Bill From', 'Bill To', and 'Signatory Name' fields.")
    else:
        with st.spinner("Generating PDF... Please wait."):
            try:
                # Get company name from first line of Bill From
                company_name = bill_from_data.split('\n')[0].strip().replace(',', '')
                
                # Filter invoice data for selected invoice ID
                sub_inv = st.session_state.invoice_df[st.session_state.invoice_df['Invoice ID'] == selected_invoice_id]
                
                if sub_inv.empty:
                    st.error("Error: No data found for selected Invoice ID.")
                else:
                    # --- Create Invoice PDF ---
                    pdf = PDFInvoice(bill_from=bill_from_data, bill_to=bill_to_data, 
                                     company_name=company_name)
                    pdf.set_auto_page_break(auto=True, margin=15)
                    pdf.add_page()
                    
                    invoice_date = format_date_only(sub_inv.iloc[0]['Invoice date'])
                    
                    pdf.set_font("Helvetica", 'B', 10)
                    pdf.set_text_color(0,0,0) # Reset color
                    pdf.cell(95, 6, f"Invoice No.: {selected_invoice_id}", border=1, align='L')
                    pdf.cell(0, 6, f"Invoice Date: {invoice_date}", border=1, align='L')
                    pdf.ln(10)
                    
                    # --- Table headers ---
                    col_names = ["Sr.", "ASIN", "HSN", "Qty", "Rate", "Amount", "GST%", "CGST", "SGST", "Total"]
                    col_widths = [8, 46, 18, 12, 18, 20, 12, 18, 18, 20] # Total 190
                    pdf.draw_invoice_table_header(col_widths, col_names)
                    
                    # --- Table data ---
                    grand_total = 0
                    total_cgst = 0
                    total_sgst = 0
                    total_amount = 0
                    total_qty = 0 
                    serial_number = 1 
                    
                    for idx, row in sub_inv.iterrows():
                        qty = int(row['Quantity'])
                        item_cost = clean_currency(row['Item Cost'])
                        rate = item_cost / qty if qty else 0
                        gst_rate_str = str(row['GST Rate']).replace('%', '').strip()
                        gst_rate = float(gst_rate_str)
                        cgst_amt = item_cost * gst_rate / 100 / 2
                        sgst_amt = item_cost * gst_rate / 100 / 2
                        total = item_cost + cgst_amt + sgst_amt
                        
                        total_amount += item_cost
                        total_cgst += cgst_amt
                        total_sgst += sgst_amt
                        grand_total += total
                        total_qty += qty 
                        
                        vals = [
                            str(serial_number), # Sr.
                            str(row['ASIN']), # ASIN (no trim)
                            str(row['HSN'])[:18], # HSN
                            str(qty), # Qty
                            f"{rate:.2f}", # Rate
                            f"{item_cost:.2f}", # Amount
                            f"{gst_rate:.0f}%", # GST%
                            f"{cgst_amt:.2f}", # CGST
                            f"{sgst_amt:.2f}", # SGST
                            f"{total:.2f}" # Total
                        ]
                        pdf.draw_invoice_table_row(col_widths, vals)
                        serial_number += 1
                    
                    # --- Draw Table Total Row ---
                    pdf.set_font("Helvetica", 'B', 9)
                    pdf.set_fill_color(230, 230, 230)
                    
                    total_label_width = col_widths[0] + col_widths[1] + col_widths[2]
                    pdf.cell(total_label_width, 7, 'TOTAL', border=1, align='R', fill=True)
                    pdf.cell(col_widths[3], 7, str(total_qty), border=1, align='R', fill=True) 
                    pdf.cell(col_widths[4], 7, '', border=1, align='C', fill=True)
                    pdf.cell(col_widths[5], 7, f"{total_amount:.2f}", border=1, align='R', fill=True)
                    pdf.cell(col_widths[6], 7, '', border=1, align='C', fill=True)
                    pdf.cell(col_widths[7], 7, f"{total_cgst:.2f}", border=1, align='R', fill=True)
                    pdf.cell(col_widths[8], 7, f"{total_sgst:.2f}", border=1, align='R', fill=True)
                    pdf.cell(col_widths[9], 7, f"{grand_total:.2f}", border=1, align='R', fill=True)
                    pdf.ln()

                    # --- Totals ---
                    pdf.draw_totals_summary(total_amount, total_cgst, total_sgst, grand_total)
                    
                    # --- Final Remarks ---
                    grand_total_words = number_to_words(grand_total)
                    pdf.draw_final_remarks(grand_total_words, auth_sig_name)
                    
                    # --- Annexure page ---
                    pdf.is_annexure_page = True
                    pdf.add_page()
                    
                    pdf.set_font('Helvetica', 'B', 14)
                    pdf.set_text_color(0,0,0)
                    pdf.cell(0, 10, 'Annexure', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
                    pdf.ln(8)
                    
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(35, 8, 'Order ID', 1, align='C', fill=True)
                    pdf.cell(45, 8, 'Invoice ID', 1, align='C', fill=True)
                    pdf.cell(0, 8, 'Address', 1, align='C', fill=True)
                    pdf.ln()
                    
                    pdf.set_font('Helvetica', '', 9)
                    inv_orders = sub_inv['Order ID'].unique().tolist()
                    
                    # --- SIMPLE LINE BREAK ANNEXURE LOOP ---
                    for oid in inv_orders:
                        order_match = st.session_state.orders_df[st.session_state.orders_df['Order ID'] == oid]
                        
                        addr = 'Address not found'
                        if not order_match.empty:
                            order_row = order_match.iloc[0]
                            addr = merge_address(order_row)

                        # 1. Wrap the address text
                        address_width_mm = pdf.w - pdf.r_margin - pdf.l_margin - 35 - 45
                        # Estimate chars per line (approx 2.2mm per char for 9pt)
                        try:
                            # A better guess: mm / (font_size_pt * 0.35 * 0.7)
                            chars_per_line = int(address_width_mm / (9 * 0.35 * 0.7)) 
                        except ZeroDivisionError:
                            chars_per_line = 45 # A safe default
                        
                        lines = textwrap.wrap(addr, width=chars_per_line, replace_whitespace=False, drop_whitespace=False)
                        if not lines:
                            lines = [''] # Ensure at least one line

                        # 2. Print the first line with all data
                        pdf.cell(35, 7, str(oid), 1, align='L')
                        pdf.cell(45, 7, str(selected_invoice_id), 1, align='L')
                        pdf.cell(0, 7, lines[0], 1, align='L') # `0` width goes to margin
                        pdf.ln()
                        
                        # 3. Print remaining lines, with blank cells for first two cols
                        if len(lines) > 1:
                            for line in lines[1:]:
                                pdf.cell(35, 7, '', 1, align='L') # Blank cell
                                pdf.cell(45, 7, '', 1, align='L') # Blank cell
                                pdf.cell(0, 7, line, 1, align='L')
                                pdf.ln()
                    
                    # --- Finalize PDF in memory ---
                    # 
                    #  THE FIX IS HERE:
                    #  pdf.output(dest='S') already returns bytes, no .encode() needed
                    #
                    pdf_bytes = pdf.output(dest='S') 
                    
                    st.session_state.pdf_bytes = pdf_bytes
                    safe_invoice_id = sanitize_filename(selected_invoice_id)
                    st.session_state.pdf_filename = f"Invoice_Annexure_{safe_invoice_id}.pdf"
                    
                    st.success("✅ PDF Generated Successfully!")
                    
            except Exception as e:
                st.error(f"An error occurred during PDF generation: {e}")
                import traceback
                st.code(traceback.format_exc())

# --- Show Download Button if PDF is ready ---
if st.session_state.pdf_bytes:
    st.download_button(
        label="Click to Download PDF",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf",
        use_container_width=True
    )

# --- Credits Label ---
st.markdown("---")
st.caption(DEFAULT_CREDITS)

