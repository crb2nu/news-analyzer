from pydantic import BaseSettings

class Settings(BaseSettings):
    eedition_user: str
    eedition_pass: str

    class Config:
        env_prefix = ''  # read variables directly
        env_file = '.env'
        env_file_encoding = 'utf-8'
