# 💳 VNPay Payment Gateway Integration (Python & Streamlit)

This project is a functional demonstration of integrating the VNPay Payment Gateway (Version 2.1.0) using Python and the Streamlit framework. It supports creating transactions, simulating payments via the VNPay Sandbox, querying transaction status, and processing refunds.

## 🚀 Key Features
- **Online Payment:** Generate secure payment URLs with HMAC-SHA512 digital signatures.
- **Result Handling (Return URL):** Validate checksums from VNPay responses to update order status securely.
- **Transaction Query (QueryDR):** Real-time API calls to verify the current status of any transaction.
- **Refund Processing:** Send refund requests to the VNPay system for successful transactions. **But this feature is currently limited in the VNPAY sandbox**
- **Transaction Management:** Persistent storage and display of transaction history using SQLite.

## 🛠 Tech Stack
- **Backend:** Python 3.10+
- **Frontend:** Streamlit
- **Database:** SQLite
- **Libraries:** `requests`, `python-dotenv`, `hashlib`, `hmac`

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hoangle/vnpay-test.git
   cd vnpay-test
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
3. **Environment Configuration:**
- Create a .env file in the root directory and populate it with your VNPay Sandbox credentials:
   ```bash
  VNP_TMN_CODE=YOUR_TMN_CODE
  VNP_HASH_SECRET=YOUR_HASH_SECRET
  VNP_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
  VNP_API_URL=https://sandbox.vnpayment.vn/merchant_webapi/api/transaction
  VNP_RETURN_URL=http://localhost:8501/
4. **Run the application:**
   ```bash
   streamlit run main.py

## 🌐 Deployment
- The application is live at: https://vnpay-sandbox-payment-gateway.streamlit.app