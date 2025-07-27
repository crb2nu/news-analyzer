from pydantic import BaseSettings
from typing import List
import random
import urllib.parse

class Settings(BaseSettings):
    # E-edition credentials
    eedition_user: str
    eedition_pass: str
    
    # SmartProxy configuration (from athena-scraper)
    smartproxy_username: str = 'spua66m4sy'
    smartproxy_password: str = '7h4nhZm69jvME~mslX'
    smartproxy_host: str = "us.smartproxy.com"
    smartproxy_ports: List[int] = [10001, 10002, 10003, 10004, 10005,
                                   10006, 10007, 10008, 10009, 10010]
    
    # OpenAI configuration
    openai_api_key: str = ""
    
    # Email configuration
    email_smtp_host: str = "smtp.sendgrid.net"
    email_smtp_port: int = 587
    email_api_key: str = ""
    email_from: str = "news-digest@yourdomain.com"
    email_to: str = ""
    
    # Database configuration
    database_url: str = "postgresql://user:pass@localhost/news_analyzer"
    
    # Storage configuration
    minio_endpoint: str = "minio.lan:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "news-cache"

    class Config:
        env_prefix = ''  # read variables directly
        env_file = '.env'
        env_file_encoding = 'utf-8'
    
    def get_random_proxy(self) -> dict:
        """Get a random proxy configuration for requests"""
        port = random.choice(self.smartproxy_ports)
        encoded_password = urllib.parse.quote_plus(self.smartproxy_password)
        proxy_url = f"http://{self.smartproxy_username}:{encoded_password}@{self.smartproxy_host}:{port}"
        return {"http": proxy_url, "https": proxy_url}
    
    def get_playwright_proxy(self) -> dict:
        """Get proxy configuration for Playwright"""
        port = random.choice(self.smartproxy_ports)
        return {
            "server": f"http://{self.smartproxy_host}:{port}",
            "username": self.smartproxy_username,
            "password": self.smartproxy_password
        }
