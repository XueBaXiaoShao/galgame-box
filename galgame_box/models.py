"""API 响应数据模型（VNDB / TouchGal / AnimeTrace）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Image(BaseModel):
    url: str | None = None


class Developer(BaseModel):
    id: str
    original: str | None = None
    name: str = ""


class Title(BaseModel):
    lang: str = ""
    title: str = ""
    official: bool = False


class VnRef(BaseModel):
    """角色出场作品（VNDB 简略字段）。"""

    id: str
    alttitle: str | None = None
    title: str | None = None
    image: Image | None = None
    rating: float | None = None


class VNDBVn(BaseModel):
    id: str
    rating: float | None = None
    released: str | None = None
    alttitle: str | None = None
    title: str = ""
    image: Image | None = None
    average: float | None = None
    length_minutes: int | None = None
    platforms: list[str] | None = None
    aliases: list[str] | None = None
    developers: list[Developer] | None = None
    titles: list[Title] | None = None


class VNDBCharacter(BaseModel):
    id: str
    name: str = ""
    original: str | None = None
    birthday: list[int] | None = None
    image: Image | None = None
    vns: list[VnRef] | None = None
    aliases: list[str] | None = None
    sex: list[str] | None = None
    waist: int | None = None
    hips: int | None = None
    bust: int | None = None
    blood_type: str | None = None
    weight: int | None = None
    height: int | None = None
    cup: str | None = None


class VNDBProducer(BaseModel):
    id: str
    name: str = ""
    original: str | None = None
    aliases: list[str] | None = None
    lang: str | None = None
    type: str | None = None


class VNDBRelease(BaseModel):
    id: str
    extlinks: list[dict] | None = None
    vns: list[VnRef] | None = None


class TouchGalItem(BaseModel):
    """TouchGal 搜索结果。uniqueId 用于访问作品页面。"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    unique_id: str = Field(alias="uniqueId")
    banner: str = ""
    name: str = ""
    type: list[str] = Field(default_factory=list)
    language: list[str] = Field(default_factory=list)
    platform: list[str] = Field(default_factory=list)
    average_rating: float = Field(default=0.0, alias="averageRating")
    tags: list[str] = Field(default_factory=list)


class ResourceLink(BaseModel):
    storage: str = ""
    size: str = ""
    content: str = ""
    code: str = ""
    password: str = ""


class Resource(BaseModel):
    """TouchGal 资源下载项。"""

    id: int
    name: str = ""
    section: str = ""
    type: list[str] = Field(default_factory=list)
    language: list[str] = Field(default_factory=list)
    note: str = ""
    platform: list[str] = Field(default_factory=list)
    links: list[ResourceLink] = Field(default_factory=list)


class TouchGalDetails(BaseModel):
    """TouchGal 作品页解析结果。"""

    title: str = ""
    third_info: list[str] = Field(default_factory=list)
    previews: list[str] = Field(default_factory=list)
    description: str = ""


class DetectedInfo(BaseModel):
    work: str = ""
    character: str = ""


class AnimeTraceData(BaseModel):
    box: list[float] = Field(default_factory=list)
    not_confident: bool = False
    character: list[DetectedInfo] = Field(default_factory=list)


class AnimeTraceResult(BaseModel):
    code: int = 0
    data: list[AnimeTraceData] = Field(default_factory=list)
    ai: bool = False
    zh_message: str | None = None
