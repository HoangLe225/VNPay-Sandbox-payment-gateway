import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_name="vnpay_test.db"):
        self.db_name = db_name
        self.create_table()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def create_table(self):
        """Tạo bảng và index. Tự động migration nếu DB cũ thiếu cột."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    order_id           TEXT PRIMARY KEY,
                    amount             INTEGER,
                    order_desc         TEXT,
                    vnp_transaction_no TEXT,
                    status             TEXT,
                    payment_date       TEXT,
                    vnp_create_date    TEXT,
                    vnp_pay_date       TEXT
                )
            """)

            # Migration: thêm cột mới nếu DB cũ chưa có
            for col in ["vnp_create_date", "vnp_pay_date"]:
                try:
                    conn.execute(f"ALTER TABLE transactions ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass  # Cột đã tồn tại

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_payment_date
                ON transactions(payment_date)
            """)

    def insert_transaction(self, order_id, amount, order_desc):
        """
        Lưu giao dịch mới với trạng thái Pending.
        INSERT OR IGNORE để tránh crash khi order_id trùng.
        """
        vnp_date = datetime.now().strftime("%Y%m%d%H%M%S")
        display_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (order_id, amount, order_desc, status, payment_date, vnp_create_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, amount, order_desc, 'Pending', display_date, vnp_date)
            )

    def update_transaction(self, order_id, vnp_transaction_no, status, vnp_pay_date=None):
        """
        Cập nhật kết quả sau khi nhận response từ VNPay.
        vnp_pay_date: lấy từ vnp_PayDate trong ReturnURL, dùng cho QueryDR/Refund sau này.
        """
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE transactions
                   SET vnp_transaction_no = ?, status = ?, vnp_pay_date = ?
                   WHERE order_id = ?""",
                (vnp_transaction_no, status, vnp_pay_date, order_id)
            )

    def get_transaction(self, order_id):
        """Lấy một giao dịch theo order_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions WHERE order_id = ?", (order_id,))
            return cursor.fetchone()

    def get_all_transactions(self):
        """Lấy toàn bộ lịch sử giao dịch."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions ORDER BY payment_date DESC")
            return cursor.fetchall()


if __name__ == "__main__":
    db = Database()
    db.insert_transaction("ORDER_123", 50000, "Thanh toán thử nghiệm")
    print("Đã tạo giao dịch mẫu thành công!")
    print("Danh sách hiện tại:", db.get_all_transactions())