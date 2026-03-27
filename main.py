import uuid
import streamlit as st
from datetime import datetime
import os
from dotenv import load_dotenv

from vnpay_utils import VNPay
from database import Database

# ─── Cấu hình ────────────────────────────────────────────────────────────────
load_dotenv()
st.set_page_config(page_title="VNPay Payment Demo", layout="wide")

db = Database()
vnpay = VNPay(
    tmn_code=os.getenv("VNP_TMN_CODE"),
    hash_secret=os.getenv("VNP_HASH_SECRET"),
    vnp_url=os.getenv("VNP_URL"),
    api_url=os.getenv("VNP_API_URL"),
)


# ─── Xử lý ReturnURL ─────────────────────────────────────────────────────────
# Đặt đầu file — trước khi render UI — để không mất query params khi re-render
def handle_return_url():
    params = st.query_params.to_dict()
    if "vnp_ResponseCode" not in params:
        return
    if "return_processed" in st.session_state:
        return

    st.session_state["return_processed"] = True
    st.query_params.clear()

    if not vnpay.validate_response(params):
        st.session_state["payment_result"] = ("invalid", "Chữ ký không hợp lệ")
        return

    order_id    = params.get("vnp_TxnRef")
    res_code    = params.get("vnp_ResponseCode")
    tran_status = params.get("vnp_TransactionStatus")
    vnp_tran_no = params.get("vnp_TransactionNo")
    vnp_amount  = int(params.get("vnp_Amount", 0))
    vnp_pay_date = params.get("vnp_PayDate")

    if res_code != "00" or tran_status != "00":
        db.update_transaction(order_id, vnp_tran_no, f"Failed ({res_code})")
        st.session_state["payment_result"] = ("failed", res_code)
        return

    # Thành công — kiểm tra DB
    existing = db.get_transaction(order_id)

    if existing is None:
        # Không tìm thấy order — giao dịch lạ
        st.session_state["payment_result"] = ("invalid", f"Không tìm thấy đơn hàng {order_id}")
        return

    expected_amount = int(existing[1]) * 100
    if vnp_amount != expected_amount:
        st.session_state["payment_result"] = (
            "invalid",
            f"Số tiền không khớp: nhận {vnp_amount}, mong đợi {expected_amount}",
        )
        return

    if existing[4] == "Success":
        # Idempotency — đã xử lý rồi, không cập nhật lại
        st.session_state["payment_result"] = ("success", order_id)
        return

    db.update_transaction(order_id, vnp_tran_no, "Success", vnp_pay_date)
    st.session_state["payment_result"] = ("success", order_id)


handle_return_url()


# ─── UI ──────────────────────────────────────────────────────────────────────
st.title("💳 VNPay Payment Gateway Integration")

if "payment_result" in st.session_state:
    result_type, result_val = st.session_state.pop("payment_result")
    if result_type == "success":
        st.balloons()
        st.success(f"✅ Thanh toán thành công đơn hàng **{result_val}**!")
    elif result_type == "failed":
        st.error(f"❌ Thanh toán thất bại. Mã lỗi: {result_val}")
    elif result_type == "invalid":
        st.warning(f"⚠️ Giao dịch không hợp lệ: {result_val}")

tab1, tab2 = st.tabs(["Tạo Thanh Toán", "Lịch Sử Giao Dịch"])

# ─── Tab 1: Tạo thanh toán ───────────────────────────────────────────────────
with tab1:
    st.header("Thông tin đơn hàng")
    default_order_id = f"ORDER_{datetime.now().strftime('%H%M%S')}"

    with st.form("payment_form"):
        order_id = st.text_input("Mã đơn hàng", value=default_order_id)
        amount = st.number_input("Số tiền (VND)", min_value=10000, step=1000, value=10000)
        # Dùng placeholder thay vì f-string phụ thuộc order_id (stale value)
        order_desc = st.text_area(
            "Nội dung thanh toán",
            placeholder="VD: Thanh toan don hang thang 3",
            help="Không dấu, không ký tự đặc biệt — yêu cầu của VNPAY",
        )
        submitted = st.form_submit_button("Tiến hành thanh toán")

    if submitted:
        # Fallback nếu user để trống mô tả
        desc = order_desc.strip() or f"Thanh toan don hang {order_id}"

        vnp_params = {
            "vnp_Version":    "2.1.0",
            "vnp_Command":    "pay",
            "vnp_TmnCode":    vnpay.tmn_code,
            "vnp_Amount":     int(amount) * 100,
            "vnp_CreateDate": datetime.now().strftime("%Y%m%d%H%M%S"),
            "vnp_CurrCode":   "VND",
            "vnp_IpAddr":     "127.0.0.1",
            "vnp_Locale":     "vn",
            "vnp_OrderInfo":  desc,
            "vnp_OrderType":  "other",
            "vnp_ReturnUrl":  os.getenv("VNP_RETURN_URL"),
            "vnp_TxnRef":     order_id,
        }

        db.insert_transaction(order_id, amount, desc)
        payment_url = vnpay.get_payment_url(vnp_params)

        st.success("Đã tạo link thanh toán!")
        st.link_button("Đến trang thanh toán VNPay →", payment_url)

# ─── Tab 2: Lịch sử giao dịch ────────────────────────────────────────────────
with tab2:
    st.header("Lịch sử giao dịch")

    if st.button("🔄 Làm mới danh sách"):
        st.rerun()

    transactions = db.get_all_transactions()

    if not transactions:
        st.info("Chưa có giao dịch nào.")
    else:
        for txn in transactions:
            # Schema:
            # txn[0] = order_id
            # txn[1] = amount
            # txn[2] = order_desc
            # txn[3] = vnp_transaction_no
            # txn[4] = status
            # txn[5] = payment_date (display)
            # txn[6] = vnp_create_date  (YYYYMMDDHHMMSS — lúc tạo order)
            # txn[7] = vnp_pay_date     (YYYYMMDDHHMMSS — lúc VNPay xử lý, dùng cho QueryDR/Refund)

            col1, col2, col3, col4 = st.columns([2, 2, 2, 3])

            with col1:
                st.write(f"**Mã:** {txn[0]}")
                st.caption(txn[5])

            with col2:
                st.write(f"**Số tiền:** {txn[1]:,} VND")

            with col3:
                current_status = txn[4]
                if current_status == "Success":
                    st.markdown(":green[✅ Success]")
                elif current_status == "Refunded":
                    st.markdown(":blue[↩️ Refunded]")
                elif current_status and current_status.startswith("Failed"):
                    st.markdown(f":red[❌ {current_status}]")
                else:
                    st.markdown(f":orange[⏳ {current_status}]")

            with col4:
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    if st.button("Check 🔍", key=f"check_{txn[0]}"):
                        order_id       = txn[0]
                        order_info     = txn[2]
                        transaction_no = txn[3] or ""
                        pay_date       = txn[7]  # vnp_PayDate — bắt buộc cho QueryDR

                        # Nếu chưa có pay_date (giao dịch chưa hoàn tất), QueryDR sẽ không có kết quả
                        # Vẫn gọi được nhưng thông báo rõ cho user
                        if not pay_date:
                            st.warning("Giao dịch chưa có ngày thanh toán — kết quả QueryDR có thể không chính xác")

                        with st.spinner("Đang kiểm tra..."):
                            result = vnpay.query_dr(
                                order_id=order_id,
                                order_info=order_info,
                                transaction_no=transaction_no,
                                transaction_date=txn[6],
                            )

                        resp_code = result.get("vnp_ResponseCode")
                        vnp_status = result.get("vnp_TransactionStatus")
                        vnp_tran_no = result.get("vnp_TransactionNo", transaction_no)

                        if resp_code == "00":
                            if vnp_status == "00":
                                db.update_transaction(order_id, vnp_tran_no, "Success", pay_date)
                                st.toast("Giao dịch thành công!", icon="✅")
                                st.rerun()
                            else:
                                # Map một số status code phổ biến để hiển thị rõ hơn
                                status_map = {
                                    "01": "Chưa hoàn tất",
                                    "02": "Giao dịch lỗi",
                                    "04": "Đảo giao dịch",
                                    "07": "Nghi ngờ gian lận",
                                    "09": "Hoàn trả bị từ chối",
                                }
                                label = status_map.get(vnp_status, f"Mã trạng thái: {vnp_status}")
                                db.update_transaction(order_id, vnp_tran_no, f"Failed ({vnp_status})")
                                st.warning(f"VNPAY phản hồi: {label}")
                                st.rerun()
                        else:
                            msg = result.get("vnp_Message", "Không có thông tin lỗi")
                            st.error(f"QueryDR thất bại [{resp_code}]: {msg}")

                with btn_col2:
                    if txn[4] == "Success":
                        if st.button("Refund 💸", key=f"refund_{txn[0]}"):
                            # Lần bấm đầu: set flag confirm, chưa gọi API
                            st.session_state[f"confirm_refund_{txn[0]}"] = True

                        # Hiện confirm dialog sau khi bấm Refund lần đầu
                        if st.session_state.get(f"confirm_refund_{txn[0]}"):
                            st.warning(f"Xác nhận hoàn tiền **{txn[1]:,} VND** cho đơn **{txn[0]}**?")
                            c1, c2 = st.columns(2)

                            with c1:
                                if st.button("✅ Xác nhận", key=f"confirm_yes_{txn[0]}"):
                                    st.session_state.pop(f"confirm_refund_{txn[0]}", None)

                                    with st.spinner("Đang hoàn tiền..."):
                                        result = vnpay.refund(
                                            order_id=txn[0],
                                            amount=int(txn[1]) * 100,
                                            order_info=txn[2],
                                            transaction_no=txn[3] or "",
                                            transaction_date=txn[6],  # vnp_CreateDate lúc tạo order
                                        )

                                    resp_code = result.get("vnp_ResponseCode")
                                    if resp_code == "00":
                                        db.update_transaction(txn[0], txn[3], "Refunded", txn[7])
                                        st.toast("Hoàn tiền thành công!", icon="💸")
                                        st.rerun()
                                    else:
                                        msg = result.get("vnp_Message", "Không có thông tin lỗi")
                                        st.error(f"Refund thất bại [{resp_code}]: {msg}")

                            with c2:
                                if st.button("❌ Hủy", key=f"confirm_no_{txn[0]}"):
                                    st.session_state.pop(f"confirm_refund_{txn[0]}", None)
                                    st.rerun()

            st.divider()