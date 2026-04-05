from pydantic import BaseModel


class GmailProfileResponse(BaseModel):
    email: str
    messages_total: int
    threads_total: int
