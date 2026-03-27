from datetime import datetime
import hashlib
import hmac
import urllib.parse
import uuid
import requests
import os


class VNPay:
    def __init__(self, tmn_code: str, hash_secret: str, vnp_url: str, api_url: str):
        self.tmn_code   = tmn_code
        self.hash_secret = hash_secret
        self.vnp_url    = vnp_url
        self.api_url    = api_url

    def get_payment_url(self, vnp_params: dict) -> str:
        hash_string, query_string = self._build_strings(vnp_params)
        signature = self._hmac_sha512(self.hash_secret, hash_string)
        return f"{self.vnp_url}?{query_string}&vnp_SecureHash={signature}"

    def validate_response(self, vnp_params: dict) -> bool:
        params = dict(vnp_params)
        received_hash = params.pop("vnp_SecureHash", None)
        params.pop("vnp_SecureHashType", None)
        if not received_hash:
            return False
        expected_hash, _ = self._build_strings(params)
        expected_hash = self._hmac_sha512(self.hash_secret, expected_hash)
        return hmac.compare_digest(received_hash.lower(), expected_hash.lower())

    def _build_strings(self, params: dict) -> tuple[str, str]:
        """
        Trả về (hash_string, query_string) từ params.
        - Loại bỏ giá trị rỗng/None
        - Sort theo key
        - quote_plus cả key lẫn value (đúng theo VNPAY docs)
        - Hai string này GIỐNG NHAU vì VNPAY dùng cùng format để verify
        """
        filtered = sorted(
            (k, v) for k, v in params.items()
            if v is not None and v != ""
        )
        parts = [
            f"{urllib.parse.quote_plus(str(k))}={urllib.parse.quote_plus(str(v))}"
            for k, v in filtered
        ]
        result = "&".join(parts)
        return result, result  # hash_string == query_string với VNPAY

    @staticmethod
    def _hmac_sha512(key: str, data: str) -> str:
        return hmac.new(
            key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()

    def query_dr(self, order_id: str, order_info: str, transaction_no: str,
                transaction_date: str, ip_addr: str = "127.0.0.1") -> dict:
        """
        Gọi API QueryDR để kiểm tra trạng thái giao dịch.
        Hash theo thứ tự cố định (KHÔNG sort) — đúng theo VNPAY docs:
        RequestId|Version|Command|TmnCode|TxnRef|OrderInfo|TransactionNo|TransactionDate|CreateDate|IpAddr
        """
        request_id  = uuid.uuid4().hex
        create_date = datetime.now().strftime("%Y%m%d%H%M%S")

        hash_data = "|".join([
            request_id,
            "2.1.0",
            "querydr",
            self.tmn_code,
            order_id,
            transaction_date,
            create_date,
            ip_addr,
            order_info,
        ])

        payload = {
            "vnp_RequestId":      request_id,
            "vnp_Version":        "2.1.0",
            "vnp_Command":        "querydr",
            "vnp_TmnCode":        self.tmn_code,
            "vnp_TxnRef":         order_id,
            "vnp_OrderInfo":      order_info,
            "vnp_TransactionNo":  transaction_no,
            "vnp_TransactionDate": transaction_date,
            "vnp_CreateDate":     create_date,
            "vnp_IpAddr":         ip_addr,
            "vnp_SecureHash":     self._hmac_sha512(self.hash_secret, hash_data),
        }

        try:
            response = requests.post(
                self.api_url,  # inject từ __init__, không gọi os.getenv trong method
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"vnp_ResponseCode": "99", "vnp_Message": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return {"vnp_ResponseCode": "99", "vnp_Message": f"Lỗi kết nối: {e}"}

    def refund(self, order_id: str, amount: int, order_info: str,
           transaction_no: str, transaction_date: str,
           create_by: str = "Admin", ip_addr: str = "127.0.0.1") -> dict:
        """
        Hash string theo đúng thứ tự docs VNPAY:
        RequestId|Version|Command|TmnCode|TransactionType|TxnRef|Amount|
        TransactionNo|TransactionDate|CreateBy|CreateDate|IpAddr|OrderInfo

        Lưu ý so với QueryDR:
        - OrderInfo ở CUỐI (giống QueryDR)
        - TransactionNo nằm TRONG hash string (khác QueryDR)
        - TransactionDate = vnp_CreateDate lúc tạo payment gốc (txn[6]), không phải PayDate
        - Amount nhân 100 trước khi truyền vào
        """
        request_id  = uuid.uuid4().hex
        create_date = datetime.now().strftime("%Y%m%d%H%M%S")

        hash_data = "|".join([
            request_id,
            "2.1.0",
            "refund",
            self.tmn_code,
            "02",                       # TransactionType: 02 = hoàn toàn phần
            order_id,
            str(amount),                # đã nhân 100 từ caller
            transaction_no,             # có trong hash (khác QueryDR)
            transaction_date,
            create_by,
            create_date,
            ip_addr,
            order_info,                 # OrderInfo ở cuối
        ])

        payload = {
            "vnp_RequestId":       request_id,
            "vnp_Version":         "2.1.0",
            "vnp_Command":         "refund",
            "vnp_TmnCode":         self.tmn_code,
            "vnp_TransactionType": "02",
            "vnp_TxnRef":          order_id,
            "vnp_Amount":          str(amount),
            "vnp_OrderInfo":       order_info,
            "vnp_TransactionNo":   transaction_no,
            "vnp_TransactionDate": transaction_date,
            "vnp_CreateBy":        create_by,
            "vnp_CreateDate":      create_date,
            "vnp_IpAddr":          ip_addr,
            "vnp_SecureHash":      self._hmac_sha512(self.hash_secret, hash_data),
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"vnp_ResponseCode": "99", "vnp_Message": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return {"vnp_ResponseCode": "99", "vnp_Message": f"Lỗi kết nối: {e}"}