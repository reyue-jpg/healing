import hmac
import pickle
import hashlib
import json
import os
from utils.logutil import get_logger
from typing import IO
from base64 import b64decode, b85encode

class SecurityError(Exception):
    pass

class SecurePickle:
    """
        序列化并保存进行过签名的Web元素
    """
    def __init__(self, secret_key: bytes=None):
        """
        初始化安全序列化器

        :param secret_key 用于 HMAC 签名秘钥(字节串)，如果不指定将会随机生成
        """
        self.logger = get_logger()

        if secret_key is None:
            self.secret_key = os.urandom(32)
        else:
            self.secret_key = secret_key

        self.digestmod = hashlib.sha256

    def dumps(self, obj: object) -> bytes:
        """
        安全的序列化对象，返回签名后的字符串
        """
        pickled_data = pickle.dumps(obj)

        signature = hmac.new(
            self.secret_key,
            pickled_data,
            self.digestmod
        ).digest()

        return signature + pickled_data

    def dump(self, obj: object, file: IO) -> bool:
        """
        安全的序列化对象，将签名后的对象保存至文件
        """
        try:
            secure_data = self.dumps(obj)
            file.write(secure_data)
            return True
        except Exception as f:
            self.logger.error(f"序列化出现异常: {f}")
            return False

    def loads(self, secure_data: bytes):
        """
        分离签名和序列化数据，尝试加载反序列化后的对象
        """
        signature_size = self.digestmod().digest_size
        handheld_signature = secure_data[:signature_size]
        pickled_data = secure_data[signature_size:]
        expected_signature = hmac.new(
            self.secret_key,
            pickled_data,
            self.digestmod
        ).digest()

        if not hmac.compare_digest(expected_signature, handheld_signature):
            raise SecurityError(f"签名验证失败！数据可能已被篡改-对象:{secure_data}")

    def load(self, file: IO[bytes]):
        """
        从文件加载反序列化对象，分离后尝试加载反序列化对象
        """
        try:
            secure_data = file.read()
            self.loads(secure_data)
        except Exception as e:
            self.logger.error(f"反序列化时出现错误{e}")

if __name__ == '__main__':
    hmac_instance = SecurePickle()
    s = "hello"
    h = hmac_instance.dumps(s)
    print(h)