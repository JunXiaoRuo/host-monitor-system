# -*- coding: utf-8 -*-
"""
阿里云OSS服务模块
负责文件上传和下载链接生成
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

try:
    import oss2
except ImportError:
    oss2 = None

logger = logging.getLogger(__name__)

class OSSService:
    """阿里云OSS服务类"""
    
    def __init__(self):
        self.bucket = None
        self.endpoint = None
        self.access_key_id = None
        self.access_key_secret = None
        self.bucket_name = None
        self.folder_path = None
    
    def configure(self, endpoint: str, access_key_id: str, access_key_secret: str, 
                 bucket_name: str, folder_path: str = "reports") -> bool:
        """
        配置OSS连接参数
        
        Args:
            endpoint: OSS endpoint
            access_key_id: Access Key ID
            access_key_secret: Access Key Secret
            bucket_name: Bucket名称
            folder_path: 存储文件夹路径
            
        Returns:
            配置是否成功
        """
        try:
            if not oss2:
                logger.error("oss2库未安装，请运行: pip install oss2")
                return False
            
            self.endpoint = endpoint
            self.access_key_id = access_key_id
            self.access_key_secret = access_key_secret
            self.bucket_name = bucket_name
            self.folder_path = folder_path.strip('/') if folder_path else "reports"
            
            # 创建认证对象
            auth = oss2.Auth(access_key_id, access_key_secret)
            
            # 创建Bucket对象
            self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
            
            # 测试连接
            try:
                self.bucket.get_bucket_info()
                logger.info(f"OSS配置成功，Bucket: {bucket_name}")
                return True
            except Exception as e:
                logger.error(f"OSS连接测试失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"OSS配置失败: {str(e)}")
            return False
    
    def upload_file(self, local_file_path: str, remote_file_name: str = None) -> Tuple[bool, str, str]:
        """
        上传文件到OSS
        
        Args:
            local_file_path: 本地文件路径
            remote_file_name: 远程文件名，如果为None则使用本地文件名
            
        Returns:
            (是否成功, 错误信息或成功信息, OSS文件路径)
        """
        try:
            if not self.bucket:
                return False, "OSS未配置", ""
            
            if not os.path.exists(local_file_path):
                return False, f"本地文件不存在: {local_file_path}", ""
            
            # 生成远程文件名
            if not remote_file_name:
                remote_file_name = os.path.basename(local_file_path)
            
            # 构建完整的OSS路径
            oss_file_path = f"{self.folder_path}/{remote_file_name}" if self.folder_path else remote_file_name
            
            # 上传文件
            with open(local_file_path, 'rb') as f:
                result = self.bucket.put_object(oss_file_path, f)
            
            if result.status == 200:
                logger.info(f"文件上传成功: {local_file_path} -> {oss_file_path}")
                return True, "文件上传成功", oss_file_path
            else:
                logger.error(f"文件上传失败，状态码: {result.status}")
                return False, f"文件上传失败，状态码: {result.status}", ""
                
        except Exception as e:
            logger.error(f"文件上传异常: {str(e)}")
            return False, f"文件上传异常: {str(e)}", ""
    
    def generate_download_url(self, oss_file_path: str, expires_in_hours: int = 24) -> Tuple[bool, str, str]:
        """
        生成文件下载链接
        
        Args:
            oss_file_path: OSS文件路径
            expires_in_hours: 链接有效期（小时）
            
        Returns:
            (是否成功, 错误信息或成功信息, 下载链接)
        """
        try:
            if not self.bucket:
                return False, "OSS未配置", ""
            
            # 生成签名URL
            expires_in_seconds = expires_in_hours * 3600
            download_url = self.bucket.sign_url('GET', oss_file_path, expires_in_seconds)
            
            logger.info(f"生成下载链接成功: {oss_file_path}，有效期: {expires_in_hours}小时")
            return True, "下载链接生成成功", download_url
            
        except Exception as e:
            logger.error(f"生成下载链接失败: {str(e)}")
            return False, f"生成下载链接失败: {str(e)}", ""
    
    def upload_and_get_url(self, local_file_path: str, remote_file_name: str = None, 
                          expires_in_hours: int = 24) -> Tuple[bool, str, str]:
        """
        上传文件并生成下载链接
        
        Args:
            local_file_path: 本地文件路径
            remote_file_name: 远程文件名
            expires_in_hours: 链接有效期（小时）
            
        Returns:
            (是否成功, 错误信息或成功信息, 下载链接)
        """
        # 上传文件
        success, message, oss_file_path = self.upload_file(local_file_path, remote_file_name)
        
        if not success:
            return False, message, ""
        
        # 生成下载链接
        success, message, download_url = self.generate_download_url(oss_file_path, expires_in_hours)
        
        if not success:
            return False, message, ""
        
        return True, "文件上传并生成下载链接成功", download_url
    
    def delete_file(self, oss_file_path: str) -> Tuple[bool, str]:
        """
        删除OSS文件
        
        Args:
            oss_file_path: OSS文件路径
            
        Returns:
            (是否成功, 错误信息或成功信息)
        """
        try:
            if not self.bucket:
                return False, "OSS未配置"
            
            result = self.bucket.delete_object(oss_file_path)
            
            if result.status == 204:
                logger.info(f"文件删除成功: {oss_file_path}")
                return True, "文件删除成功"
            else:
                logger.error(f"文件删除失败，状态码: {result.status}")
                return False, f"文件删除失败，状态码: {result.status}"
                
        except Exception as e:
            logger.error(f"文件删除异常: {str(e)}")
            return False, f"文件删除异常: {str(e)}"
    
    def is_configured(self) -> bool:
        """
        检查OSS是否已配置
        
        Returns:
            是否已配置
        """
        return self.bucket is not None
    
    @staticmethod
    def is_oss2_available() -> bool:
        """
        检查oss2库是否可用
        
        Returns:
            oss2库是否可用
        """
        return oss2 is not None