import hmac
import pickle
import hashlib
import json
import os

from utils.logutil import get_logger
from utils.logutil.logutil import BuildLogger
from typing import IO, Optional, Union, Any, Dict
from base64 import b64decode, b64encode


class SecurityError(Exception):
    """签名验证失败时抛出的异常。"""


class SecurePickle:
    """
    序列化并保存进行过签名的对象。
    """

    def __init__(self, secret_key: Optional[bytes] = None, algorithm="sha256", file_name="plk_element.json"):
        """
        初始化安全序列化器。

        :param secret_key: 用于 HMAC 签名秘钥（字节串），不指定则随机生成
        """
        self.logger = get_logger()

        if os.path.dirname(file_name):
            self.file_name = file_name
            self.logger.debug(f"已指定加密元素文件保存位置: {self.file_name}")
        else:
            self.file_name = os.path.join(BuildLogger.get_root_dir(), file_name)
            self.logger.debug("加密元素文件生成在根目录")

        if algorithm == "sha256":
            self.digestmod = hashlib.sha256
        elif algorithm == "sha512":
            self.digestmod = hashlib.sha512
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        if secret_key is None:
            self.secret_key = os.urandom(32)
            self.logger.debug("生成了新的密钥")
        else:
            self.secret_key = secret_key

        self.signature_size = self.digestmod().digest_size

    def dumps(self, obj: object) -> bytes:
        """安全序列化对象，返回签名后的字节串。"""
        pickled_data = pickle.dumps(obj)
        signature = hmac.new(
            self.secret_key,
            pickled_data,
            self.digestmod
        ).digest()
        return signature + pickled_data

    def dump(self, obj: object, file: IO) -> bool:
        """安全序列化对象并写入文件。"""
        try:
            secure_data = self.dumps(obj)
            file.write(secure_data)
            return True
        except Exception as exc:
            self.logger.error(f"序列化出现异常: {exc}")
            return False

    def loads(self, secure_data: bytes) -> Any:
        """校验签名后反序列化对象。"""
        handheld_signature = secure_data[:self.signature_size]
        pickled_data = secure_data[self.signature_size:]
        expected_signature = hmac.new(
            self.secret_key,
            pickled_data,
            self.digestmod
        ).digest()

        if not hmac.compare_digest(expected_signature, handheld_signature):
            raise SecurityError(f"签名验证失败，数据可能被篡改: {secure_data}")

        return pickle.loads(pickled_data)

    def load(self, file: IO[bytes]) -> Any:
        """从文件读取并反序列化对象。"""
        try:
            secure_data = file.read()
            return self.loads(secure_data)
        except Exception as exc:
            self.logger.error(f"反序列化时出现错误: {exc}")
            raise

    def to_json_safe(self, obj: object, json_file: Optional[str] = None) -> Dict[str, Any]:
        """
        将对象转换为 JSON 安全格式并保存到文件。

        :param obj: 要序列化的对象
        :param json_file: JSON 文件路径，不传时使用 self.file_name
        :return: 转换后的字典
        """
        secure_data = self.dumps(obj)
        signature = secure_data[:self.signature_size]
        data = secure_data[self.signature_size:]

        result = {
            "signature": b64encode(signature).decode("utf-8"),
            "data": b64encode(data).decode("utf-8"),
            "algorithm": self.digestmod().name
        }
        file_path = json_file or self.file_name
        with open(file_path, "w", encoding="utf-8") as file_obj:
            json.dump(result, file_obj, ensure_ascii=False, indent=4)

        self.logger.info(f"已保存加密对象到: {file_path}")
        return result

    def from_json_safe(self, json_data: Optional[Union[Dict[str, Any], str]] = None) -> Any:
        """
        从 JSON 文件或字典加载安全格式并反序列化。

        :param json_data: JSON 文件路径、JSON 字符串或字典，不传时使用 self.file_name
        :return: 反序列化对象
        """
        loaded_data = None

        if json_data is None:
            json_file = self.file_name
            if not os.path.exists(json_file):
                raise ValueError(f"JSON 文件不存在: {json_file}")
            self.logger.info(f"加载元素文件: {json_file}")
            with open(json_file, "r", encoding="utf-8") as file_obj:
                try:
                    loaded_data = json.load(file_obj)
                except json.JSONDecodeError as exc:
                    raise ValueError("无效的 JSON 数据") from exc
        elif isinstance(json_data, str):
            if os.path.exists(json_data):
                self.logger.info(f"加载元素文件: {json_data}")
                with open(json_data, "r", encoding="utf-8") as file_obj:
                    try:
                        loaded_data = json.load(file_obj)
                    except json.JSONDecodeError as exc:
                        raise ValueError("无效的 JSON 数据") from exc
            else:
                try:
                    loaded_data = json.loads(json_data)
                except json.JSONDecodeError as exc:
                    raise ValueError("无效的 JSON 数据") from exc
        elif isinstance(json_data, dict):
            loaded_data = json_data
        else:
            raise ValueError("json_data 必须是文件路径字符串、JSON 字符串或字典")

        if "signature" not in loaded_data or "data" not in loaded_data:
            raise ValueError("无效的 JSON 安全格式")

        signature = b64decode(loaded_data["signature"])
        data = b64decode(loaded_data["data"])

        secure_data = signature + data
        return self.loads(secure_data)

    def export_key(self) -> str:
        """导出 Base64 格式密钥字符串。"""
        return b64encode(self.secret_key).decode("utf-8")

    @classmethod
    def import_key(cls, base64_key: str, algorithm: str, **kwargs) -> "SecurePickle":
        """
        从 Base64 字符串导入密钥并创建新实例。

        :param base64_key: Base64 格式密钥字符串
        :param algorithm: 哈希算法类型
        :return: SecurePickle 实例
        """
        secret_key = b64decode(base64_key.encode("utf-8"))
        return cls(secret_key=secret_key, algorithm=algorithm, **kwargs)
