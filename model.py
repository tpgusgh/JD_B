from pydantic import BaseModel

class Order(BaseModel):
    sugar: str
    coffee: str
    water: str
    iced_tea: str
    green_tea: str
    name: str
    room: str
    status: str = "배달준비중"