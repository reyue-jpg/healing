"""
headling/security/secure_pickle.py

安全序列化模块。
使用 HMAC + pickle 对对象进行签名序列化，防止本地缓存被篡改。
最终落盘格式为 JSON（Base64 编码），方便跨环境读取。
"""

import hmac, pickle, hashlib, json, os
from base64 import b64decode, b64encode
from typing import IO, Optional, Union, Any, Dict


class SecurityError(Exception):
    """签名验证失败时抛出的异常。"""


class SecurePickle:
    def __init__(self, secret_key=None, algorithm="sha256", file_name="plk_element.json"):
        if algorithm == "sha256":
            self.digestmod = hashlib.sha256
        elif algorithm == "sha512":
            self.digestmod = hashlib.sha512
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        if os.path.dirname(file_name):
            self.file_name = file_name
        else:
            self.file_name = os.path.join(_find_project_root(), file_name)

        self.secret_key = secret_key if secret_key is not None else os.urandom(32)
        self.signature_size = self.digestmod().digest_size

    def dumps(self, obj):
        pickled = pickle.dumps(obj)
        sig = hmac.new(self.secret_key, pickled, self.digestmod).digest()
        return sig + pickled

    def loads(self, secure_data):
        sig_got  = secure_data[:self.signature_size]
        pickled  = secure_data[self.signature_size:]
        sig_want = hmac.new(self.secret_key, pickled, self.digestmod).digest()
        if not hmac.compare_digest(sig_want, sig_got):
            raise SecurityError("签名验证失败，数据可能被篡改")
        return pickle.loads(pickled)

    def dump(self, obj, file):
        try:
            file.write(self.dumps(obj))
            return True
        except Exception:
            return False

    def load(self, file):
        return self.loads(file.read())

    def to_json_safe(self, obj, json_file=None):
        secure = self.dumps(obj)
        sig  = secure[:self.signature_size]
        data = secure[self.signature_size:]
        result = {
            "signature": b64encode(sig).decode("utf-8"),
            "data":      b64encode(data).decode("utf-8"),
            "algorithm": self.digestmod().name,
        }
        path = json_file or self.file_name
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    def from_json_safe(self, json_data=None):
        loaded = None
        if json_data is None:
            path = self.file_name
            if not os.path.exists(path):
                raise FileNotFoundError(f"元素缓存文件不存在: {path}")
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        elif isinstance(json_data, str):
            if os.path.exists(json_data):
                with open(json_data, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            else:
                loaded = json.loads(json_data)
        elif isinstance(json_data, dict):
            loaded = json_data
        else:
            raise ValueError("json_data 必须是文件路径、JSON 字符串或 dict")

        if "signature" not in loaded or "data" not in loaded:
            raise ValueError("无效的 JSON 安全格式")
        sig  = b64decode(loaded["signature"])
        data = b64decode(loaded["data"])
        return self.loads(sig + data)

    def export_key(self):
        return b64encode(self.secret_key).decode("utf-8")

    @classmethod
    def import_key(cls, base64_key, algorithm="sha256", **kwargs):
        return cls(secret_key=b64decode(base64_key.encode("utf-8")),
                   algorithm=algorithm, **kwargs)


def _find_project_root():
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        for marker in ("requirements.txt", "README.md"):
            if os.path.exists(os.path.join(cur, marker)):
                return cur
        cur = os.path.dirname(cur)
    return os.getcwd()
