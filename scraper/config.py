from pydantic_settings import BaseSettings
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
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: str = "1000"
    
    # Ntfy configuration (replacing email)
    ntfy_url: str = "http://ntfy-service.news-analyzer.svc.cluster.local"
    ntfy_topic: str = "news-digest"
    ntfy_token: str = ""  # Optional auth token
    ntfy_attach_full: bool = False  # Whether to attach full digest as file
    
    # Slack configuration (optional)
    slack_webhook_url: str = ""
    
    # Database configuration
    database_url: str = "postgresql://news_analyzer:changeme-strong-password-here@postgres-service:5432/news_analyzer"
    
    # Storage configuration
    minio_endpoint: str = "minio-service.news-analyzer.svc.cluster.local"
    minio_access_key: str = "news-analyzer"
    minio_secret_key: str = "changeme-strong-secret-key"
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
