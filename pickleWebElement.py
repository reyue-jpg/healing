import hmac
import pathlib
import pickle
import hashlib
import json
import os
from utils.logutil import get_logger
from utils.logutil.logutil import BuildLogger
from pathlib import Path
from typing import IO, Optional, Union, Any, Dict
from base64 import b64decode, b64encode


class SecurityError(Exception):
    pass

class SecurePickle:
    """
        序列化并保存进行过签名的Web元素
    """
    def __init__(self, secret_key: Optional[bytes]=None, algorithm='sha256', file_name = 'plk_element.json'):
        """
        初始化安全序列化器

        :param secret_key 用于 HMAC 签名秘钥(字节串)，如果不指定将会随机生成
        """
        self.logger = get_logger()

        if algorithm == 'sha256':
            self.digestmod = hashlib.sha256
        elif algorithm == 'sha512':
            self.digestmod = hashlib.sha512

        if secret_key is None:
            self.secret_key = os.urandom(32)
            self.logger.debug("生成了新的密钥")
        else:
            self.secret_key = secret_key

        self.signature_size = self.digestmod().digest_size

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

    def loads(self, secure_data: bytes) -> Any:
        """
        分离签名和序列化数据，尝试加载反序列化后的对象
        """
        handheld_signature = secure_data[:self.signature_size]
        pickled_data = secure_data[self.signature_size:]
        expected_signature = hmac.new(
            self.secret_key,
            pickled_data,
            self.digestmod
        ).digest()

        if not hmac.compare_digest(expected_signature, handheld_signature):
            raise SecurityError(f"签名验证失败！数据可能已被篡改-对象:{secure_data}")

        return pickle.loads(pickled_data)

    def load(self, file: IO[bytes]) -> Any:
        """
        从文件加载反序列化对象，分离后尝试加载反序列化对象
        """
        try:
            secure_data = file.read()
            return self.loads(secure_data)
        except Exception as e:
            self.logger.error(f"反序列化时出现错误{e}")
            raise

    def to_json_safe(self, obj: object) -> Path:
        """
        将安全格式转换为json格式
        """
        secure_data = self.dumps(obj)
        signature = secure_data[:self.signature_size]
        data = secure_data[self.signature_size:]

        result = {
            'signature': b64encode(signature).decode('utf-8'),
            'data': b64encode(data).decode('utf-8'),
            'algorithm': self.digestmod().name
        }

        with open(self.file_name, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

    def from_json_safe(self, json_data: Optional[Union[Dict[str, Any], str]]) -> Any:
        """
        从json文件加载
        """
        if os.path.exists(json_data):
            if os.path.isfile(os.path.split(json_data)[1]):
                data = json.loads(json_data)
                print(data)

    def export_key(self):
        pass

if __name__ == '__main__':
    hmac_instance = SecurePickle()
    s = "hello"
    h = hmac_instance.to_json_safe(s)
    print(h)