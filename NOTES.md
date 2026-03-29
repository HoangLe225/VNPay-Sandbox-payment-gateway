# Technical Notes & Problem Solving

## 1. Understanding the Payment Flow
The integration strictly follows VNPay's secure transaction lifecycle:
1. **Initialization:** The client submits order details -> The server generates a Hash (Checksum) using the Secret Key -> Redirects the user to the VNPay gateway.
2. **Verification:** Upon completion, VNPay redirects to the `Return URL` with result parameters. The server recalculates the Hash from these parameters and compares it with the received `vnp_SecureHash`. Data is only trusted if the hashes match.
3. **Reconciliation:** The `QueryDR` API is implemented to proactively verify transaction status in cases where the user closes the browser prematurely or network issues occur.

## 2. Challenges & Solutions
- **"Request is duplicated" Error:** This occurred due to overlapping `vnp_RequestId` values in the Sandbox environment.
    * **Solution:** It is because of the time limit for dupilcated request of VNPAY (next request limited within 5 minutes).
- **Checksum Logic Errors:** Different APIs (Pay vs. QueryDR vs. Refund) require different parameter ordering in the pipe-delimited (`|`) hash string.
    * **Solution:** I cross-referenced the VNPay 2.1.0 documentation to fix the hashing order, specifically correctly positioning `vnp_OrderInfo` which varies per API type.

## 3. Problems
- **"Refund feature is limited"** This feature is still limited in the VNPAY sandbox.

## 4. Future Enhancements
In a production environment, I would transition from SQLite to another DB for better concurrency and integrate an **Asynchronous IPN (Instant Payment Notification)** worker to ensure order statuses are updated even if the Return URL is never reached by the user.