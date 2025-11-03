import logging
import os
import shutil
import winreg
import subprocess
import requests
from typing import Optional
from utils.logutil.logutil import BuildLogger
from utils.configutil.configutil import IniConfigHandler
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService

from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager


class DriverCompatibilityChecker:
    """驱动兼容性检查器"""

    @staticmethod
    def check_driver_compatibility(browser_type):
        """
        检查驱动与浏览器兼容性

        :param browser_type: 浏览器类型 (chrome/firefox/edge)
        :return: (是否兼容, 消息)
        """
        browser_type = browser_type.lower()

        try:
            # 获取浏览器版本
            browser_version = DriverCompatibilityChecker._get_browser_version(browser_type)
            if not browser_version:
                return False, f"无法检测到{browser_type}浏览器版本"

            # 获取环境变量中的驱动路径
            driver_path = DriverCompatibilityChecker._get_driver_path_from_env(browser_type)
            if driver_path and os.path.exists(driver_path):
                # 检查实际驱动文件的版本
                actual_driver_version = DriverCompatibilityChecker._get_actual_driver_version(driver_path, browser_type)
                if actual_driver_version:
                    # 检查实际驱动版本与浏览器是否兼容
                    browser_major = browser_version.split('.')[0]
                    driver_major = actual_driver_version.split('.')[0]

                    if browser_major == driver_major:
                        return True, f"实际驱动版本 {actual_driver_version} 与浏览器版本 {browser_version} 兼容"
                    else:
                        return False, f"实际驱动版本 {actual_driver_version} 与浏览器版本 {browser_version} 不匹配"

            # 如果无法获取实际驱动版本，检查最新可用驱动版本
            latest_driver_version = DriverCompatibilityChecker._get_latest_driver_version(browser_type)
            if latest_driver_version:
                browser_major = browser_version.split('.')[0]
                driver_major = latest_driver_version.split('.')[0]

                if browser_major == driver_major:
                    return True, f"浏览器版本 {browser_version} 与最新驱动版本 {latest_driver_version} 兼容"
                else:
                    return False, f"版本不匹配: 浏览器 {browser_version} vs 最新驱动 {latest_driver_version}"
            else:
                return False, f"无法获取{browser_type}驱动版本"

        except Exception as e:
            return False, f"兼容性检查失败: {e}"

    @staticmethod
    def _get_driver_path_from_env(browser_type):
        """从环境变量获取驱动路径"""
        if browser_type in ['chrome', 'c']:
            return os.environ.get('APP_CHROME')
        elif browser_type in ['firefox', 'f']:
            return os.environ.get('APP_FIREFOX')
        elif browser_type in ['edge', 'e']:
            return os.environ.get('APP_EDGE')
        return None

    @staticmethod
    def _get_actual_driver_version(driver_path, browser_type):
        """获取实际驱动文件的版本"""
        try:
            if browser_type in ['chrome', 'c']:
                result = subprocess.run([driver_path, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # ChromeDriver 输出格式: "ChromeDriver 91.0.4472.101 (...)"
                    output = result.stdout.strip()
                    if 'ChromeDriver' in output:
                        return output.split(' ')[1]

            elif browser_type in ['firefox', 'f']:
                result = subprocess.run([driver_path, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # GeckoDriver 输出格式: "geckodriver 0.29.1"
                    output = result.stdout.strip()
                    if 'geckodriver' in output:
                        return output.split(' ')[1]

            elif browser_type in ['edge', 'e']:
                result = subprocess.run([driver_path, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # EdgeDriver 输出格式: "Microsoft Edge WebDriver 91.0.864.59 (...)"
                    output = result.stdout.strip()
                    if 'Microsoft Edge WebDriver' in output:
                        return output.split(' ')[3]

            return None
        except Exception as e:
            print(f"获取实际驱动版本失败: {e}")
            return None

    @staticmethod
    def _get_browser_version(browser_type):
        """获取浏览器版本"""
        try:
            if browser_type in ['chrome', 'c']:
                return DriverCompatibilityChecker._get_chrome_version()
            elif browser_type in ['firefox', 'f']:
                return DriverCompatibilityChecker._get_firefox_version()
            elif browser_type in ['edge', 'e']:
                return DriverCompatibilityChecker._get_edge_version()
            else:
                return None
        except Exception as e:
            print(f"获取 {browser_type} 浏览器版本失败: {e}")
            return None

    @staticmethod
    def _get_chrome_version():
        """获取Chrome浏览器版本"""
        try:
            # 通过注册表获取
            reg_paths = [
                r"SOFTWARE\Google\Chrome\BLBeacon",
                r"SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon"
            ]

            for reg_path in reg_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                        version, _ = winreg.QueryValueEx(key, "version")
                        return version
                except FileNotFoundError:
                    continue

            # 通过命令行获取
            result = subprocess.run([
                'reg', 'query',
                r'HKCU\SOFTWARE\Google\Chrome\BLBeacon',
                '/v', 'version'
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'version' in line and 'REG_SZ' in line:
                        return line.split('REG_SZ')[-1].strip()

            return None
        except Exception:
            return None

    @staticmethod
    def _get_firefox_version():
        """获取Firefox浏览器版本"""
        try:
            # Firefox通常通过安装路径获取
            firefox_paths = [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
            ]

            for path in firefox_paths:
                if os.path.exists(path):
                    try:
                        info = subprocess.run([
                            'wmic', 'datafile', 'where',
                            f'name="{path}"', 'get', 'Version'
                        ], capture_output=True, text=True, timeout=10)

                        if info.returncode == 0:
                            lines = info.stdout.strip().split('\n')
                            if len(lines) > 1:
                                return lines[1].strip()
                    except:
                        continue
            return None
        except Exception:
            return None

    @staticmethod
    def _get_edge_version():
        """获取Edge浏览器版本"""
        try:
            # 通过注册表获取
            reg_paths = [
                r"SOFTWARE\Microsoft\Edge\BLBeacon",
                r"SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon"
            ]

            for reg_path in reg_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                        version, _ = winreg.QueryValueEx(key, "version")
                        return version
                except FileNotFoundError:
                    continue

            # 通过命令行获取
            result = subprocess.run([
                'reg', 'query',
                r'HKCU\SOFTWARE\Microsoft\Edge\BLBeacon',
                '/v', 'version'
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'version' in line and 'REG_SZ' in line:
                        return line.split('REG_SZ')[-1].strip()

            return None
        except Exception:
            return None

    @staticmethod
    def _get_latest_driver_version(browser_type):
        """使用webdriver-manager获取最新的驱动版本"""
        try:
            if browser_type in ['chrome', 'c']:
                driver_manager = ChromeDriverManager()
                latest_version = driver_manager.driver.get_latest_release_version()
                return latest_version

            elif browser_type in ['firefox', 'f']:
                driver_manager = GeckoDriverManager()
                latest_version = driver_manager.driver.get_latest_release_version()
                return latest_version

            elif browser_type in ['edge', 'e']:
                driver_manager = EdgeChromiumDriverManager()
                latest_version = driver_manager.driver.get_latest_release_version()
                return latest_version

            else:
                return None
        except Exception as e:
            print(f"获取最新驱动版本失败: {e}")
            return None


class SeleniumDriver:
    """
    Selenium 浏览器驱动管理类

    :param logger: 可选的日志记录器实例
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.driver = None
        self.logger = logger or BuildLogger(use_console=True).get_logger()

    def get_driver(self, driver_name: str, url: str, auto_download=True, force_check=True):
        """
        获取并初始化浏览器驱动

        :param driver_name: 浏览器名称 (chrome/firefox/edge 或其首字母)
        :param url: 要访问的URL
        :param auto_download: 是否自动下载兼容的驱动
        :param force_check: 是否强制检查实际驱动文件版本
        :return: 初始化后的浏览器驱动实例
        """
        driver_name = driver_name.lower()

        # 在初始化前检查兼容性
        is_compatible, message = DriverCompatibilityChecker.check_driver_compatibility(driver_name)
        self.logger.info(f"兼容性检查: {message}")

        if not is_compatible and auto_download:
            self.logger.warning("检测到版本不兼容，将尝试自动下载兼容驱动...")
            return self._get_driver_with_auto_download(driver_name, url)
        elif not is_compatible:
            self.logger.error("驱动与浏览器版本不兼容，且未启用自动下载")
            # 如果强制检查，不允许使用不兼容的驱动
            if force_check:
                raise ValueError(f"驱动与浏览器版本不兼容: {message}")
            else:
                self.logger.warning("强制检查已禁用，尝试使用现有驱动...")
                return self._try_existing_driver(driver_name, url)

        # 如果兼容，使用原有逻辑
        if driver_name in ['chrome', 'c']:
            return self._setup_chrome_driver(url)
        elif driver_name in ['firefox', 'f']:
            return self._setup_firefox_driver(url)
        elif driver_name in ['edge', 'e']:
            return self._setup_edge_driver(url)
        else:
            self.logger.error("仅支持 Chrome | Firefox | Edge 浏览器")
            raise ValueError("不支持的浏览器")

    def _try_existing_driver(self, driver_name: str, url: str):
        """尝试使用现有驱动"""
        try:
            if driver_name in ['chrome', 'c']:
                return self._setup_chrome_driver(url)
            elif driver_name in ['firefox', 'f']:
                return self._setup_firefox_driver(url)
            elif driver_name in ['edge', 'e']:
                return self._setup_edge_driver(url)
        except Exception as e:
            self.logger.error(f"使用现有驱动失败: {e}")
            raise ValueError(f"驱动不兼容且自动下载失败: {e}")

    def _get_driver_with_auto_download(self, driver_name: str, url: str):
        """使用自动下载的兼容驱动"""
        try:
            if driver_name in ['chrome', 'c']:
                driver_path = ChromeDriverManager().install()
                if os.path.exists(driver_path):
                    self.logger.info(f"ChromeDriver 下载成功: {driver_path}")
                    chrome_env = os.path.split(os.environ["APP_CHROME"])[0]
                    target_path = os.path.join(chrome_env, os.path.basename(driver_path))
                    self.logger.info(f"准备移动文件 {target_path}")
                    # 移动文件
                    shutil.move(driver_path, target_path)
                service = ChromeService(executable_path=driver_path)
                chrome_options = self._get_chrome_options()
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.info(f'Chrome 浏览器初始化，使用自动下载驱动: {driver_path}')

            elif driver_name in ['firefox', 'f']:
                driver_path = GeckoDriverManager().install()
                service = FirefoxService(executable_path=driver_path)
                firefox_options = self._get_firefox_options()
                self.driver = webdriver.Firefox(service=service, options=firefox_options)
                self.logger.info(f'Firefox 浏览器初始化，使用自动下载驱动: {driver_path}')

            elif driver_name in ['edge', 'e']:
                # 对于Edge，先检查可用版本
                available_versions = DriverCompatibilityChecker.get_available_edge_versions()
                if available_versions:
                    self.logger.info(f"可用Edge驱动版本: {available_versions}")

                # 尝试下载最新稳定版
                try:
                    driver_path = EdgeChromiumDriverManager().install()
                except Exception as e:
                    self.logger.warning(f"下载最新Edge驱动失败: {e}")
                    # 如果最新版失败，尝试使用浏览器主版本号
                    browser_version = DriverCompatibilityChecker._get_edge_version()
                    if browser_version:
                        major_version = browser_version.split('.')[0]
                        self.logger.info(f"尝试下载Edge {major_version} 版本驱动")
                        try:
                            driver_path = EdgeChromiumDriverManager(version=major_version).install()
                        except Exception as e2:
                            self.logger.error(f"下载Edge {major_version} 版本驱动也失败: {e2}")
                            raise
                    else:
                        raise

                service = EdgeService(executable_path=driver_path)
                edge_options = self._get_edge_options()
                self.driver = webdriver.Edge(service=service, options=edge_options)
                self.logger.info(f'Edge 浏览器初始化，使用自动下载驱动: {driver_path}')

            # 导航到指定URL
            self.driver.get(url)
            return self.driver

        except Exception as e:
            self.logger.error(f"自动下载驱动失败: {e}")
            self.logger.error("建议手动下载对应版本的驱动并配置环境变量")
            if driver_name in ['chrome', 'c']:
                self.logger.error("Chrome驱动下载地址: https://chromedriver.chromium.org/")
            elif driver_name in ['edge', 'e']:
                self.logger.error(
                    "Edge驱动下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            raise

    def _setup_chrome_driver(self, url: str):
        """设置Chrome驱动"""
        # 从环境变量获取 ChromeDriver 路径
        chrome_driver_path = os.environ.get('APP_CHROME')
        if not chrome_driver_path:
            self.logger.error("未找到 ChromeDriver 路径环境变量 (APP_CHROME)")
            raise ValueError("ChromeDriver 路径未配置")

        # 验证驱动文件是否存在
        if not os.path.exists(chrome_driver_path):
            self.logger.error(f"ChromeDriver 文件不存在: {chrome_driver_path}")
            raise ValueError("ChromeDriver 文件不存在")

        # 创建 Chrome 选项
        chrome_options = self._get_chrome_options()

        # 创建服务并指定驱动程序路径
        service = ChromeService(executable_path=chrome_driver_path)

        # 初始化驱动
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.logger.info(f'Chrome 浏览器初始化，使用驱动: {chrome_driver_path}')

        # 导航到指定URL
        self.driver.get(url)
        return self.driver

    def _setup_firefox_driver(self, url: str):
        """设置Firefox驱动"""
        # 从环境变量获取 GeckoDriver 路径
        firefox_driver_path = os.environ.get('APP_FIREFOX')
        if not firefox_driver_path:
            self.logger.error("未找到 GeckoDriver 路径环境变量 (APP_FIREFOX)")
            raise ValueError("GeckoDriver 路径未配置")

        # 验证驱动文件是否存在
        if not os.path.exists(firefox_driver_path):
            self.logger.error(f"GeckoDriver 文件不存在: {firefox_driver_path}")
            raise ValueError("GeckoDriver 文件不存在")

        # 创建 Firefox 选项
        firefox_options = self._get_firefox_options()

        # 创建服务并指定驱动程序路径
        service = FirefoxService(executable_path=firefox_driver_path)

        # 初始化驱动
        self.driver = webdriver.Firefox(service=service, options=firefox_options)
        self.logger.info(f'Firefox 浏览器初始化，使用驱动: {firefox_driver_path}')

        # 导航到指定URL
        self.driver.get(url)
        return self.driver

    def _setup_edge_driver(self, url: str):
        """设置Edge驱动"""
        # 从环境变量获取 EdgeDriver 路径
        edge_driver_path = os.environ.get('APP_EDGE')
        if not edge_driver_path:
            self.logger.error("未找到 EdgeDriver 路径环境变量 (APP_EDGE)")
            raise ValueError("EdgeDriver 路径未配置")

        # 验证驱动文件是否存在
        if not os.path.exists(edge_driver_path):
            self.logger.error(f"EdgeDriver 文件不存在: {edge_driver_path}")
            raise ValueError("EdgeDriver 文件不存在")

        # 创建 Edge 选项
        edge_options = self._get_edge_options()

        # 创建服务并指定驱动程序路径
        service = EdgeService(executable_path=edge_driver_path)

        # 初始化驱动
        try:
            self.driver = webdriver.Edge(service=service, options=edge_options)
            self.logger.info(f'Edge 浏览器初始化，使用驱动: {edge_driver_path}')
        except Exception as e:
            self.logger.error(f"Edge驱动初始化失败: {e}")
            raise

        # 导航到指定URL
        self.driver.get(url)
        return self.driver

    def _get_chrome_options(self):
        """获取Chrome浏览器选项"""
        chrome_options = webdriver.ChromeOptions()
        # 添加常用选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--start-maximized')
        # 移除自动化控制特征
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        return chrome_options

    def _get_firefox_options(self):
        """获取Firefox浏览器选项"""
        firefox_options = webdriver.FirefoxOptions()
        # 添加常用选项
        firefox_options.add_argument('--start-maximized')
        return firefox_options

    def _get_edge_options(self):
        """获取Edge浏览器选项"""
        edge_options = webdriver.EdgeOptions()
        # 添加常用选项
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--start-maximized')
        # 移除自动化控制特征
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        return edge_options

    def quit_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("浏览器已关闭")


if __name__ == '__main__':
    handler = IniConfigHandler()
    try:
        driver = SeleniumDriver()
        # 测试兼容性检查
        compatible, msg = DriverCompatibilityChecker.check_driver_compatibility("c")
        print(f"兼容性检查结果: {msg}")

        # 如果兼容则使用现有驱动，否则自动下载
        driver.get_driver("c", "https://www.baidu.com", auto_download=True, force_check=True)
    except Exception as e:
        print(f"驱动初始化失败: {e}")
    finally:
        handler.cleanup_env()