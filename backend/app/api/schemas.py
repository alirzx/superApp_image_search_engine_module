from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1,max_length=100)


class TextSearch(BaseModel):
    collection_id: str = 'default'
    query: str = Field(min_length=1,max_length=512)
    top_k: int = Field(default=10,ge=1,le=500)
