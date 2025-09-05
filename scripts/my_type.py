from pydantic import BaseModel


class Dream(BaseModel):
  case_id: str
  dream_id: str
  date: str
  dream_text: str
  state_of_mind: str
  notes: str