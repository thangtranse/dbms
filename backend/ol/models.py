from datetime import date as Date
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field

Tag = Annotated[str, Field(min_length=1, max_length=64)]
UserId = Annotated[str, Field(min_length=1, max_length=64)]

Budget = Literal["duoi-35", "35-50", "tren-50"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Context(Input):
    weather: Literal["nang-nong", "mua", "mat"]
    budget: Budget
    breakTime: Literal[15, 30, 60]
    mood: Literal["an-nhe", "no-bung", "healthy", "gi-cung-duoc"]
    groupSize: int = Field(default=1, ge=1, le=20)


class DishInput(Input):
    itemId: int = Field(gt=0, le=2147483647)
    name: str = Field(min_length=1, max_length=200)
    price: int = Field(ge=0, le=100000000)
    categoryId: int = Field(default=0, ge=0, le=6)
    tags: list[Tag] = Field(default_factory=list, max_length=30)
    image: str = Field(default="", max_length=1000)


class MealInput(Input):
    date: Date
    itemIds: list[int] = Field(min_length=1, max_length=300)
    label: Literal["yes", "no"]
    context: Context | None = None


class ProfilePatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    team: str | None = Field(default=None, max_length=100)
    diet: Literal["binh-thuong", "chay", "it-tinh-bot"] | None = None
    avoid: list[Tag] | None = Field(default=None, max_length=30)
    spicy: int | None = Field(default=None, ge=0, le=3)
    budget: Budget | None = None
    likedItemIds: list[int] | None = Field(default=None, max_length=300)


class Recommend(Input):
    context: Context
    exclude: list[int] = Field(default_factory=list, max_length=300)
    members: list[UserId] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=4, ge=1, le=30)


class MealPatch(Input):
    date: Date | None = None
    itemIds: list[int] | None = Field(default=None, min_length=1, max_length=300)
    label: Literal["yes", "no"] | None = None
    context: Context | None = None
