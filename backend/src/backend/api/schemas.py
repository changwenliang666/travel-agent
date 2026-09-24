from pydantic import BaseModel


class LoginBody(BaseModel):
    username: str
    password: str


class MessageBody(BaseModel):
    text: str


class PrefsBody(BaseModel):
    home_city: str = ""
    pace: str = ""
    budget: str = ""
    diet: str = ""
    early_start: bool = False
