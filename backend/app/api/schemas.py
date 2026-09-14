"""HTTP 请求模型；不向业务服务传递 Request 或 Depends 对象。"""

from pydantic import BaseModel, Field, field_validator

from ..user_settings import ALLOWED_LLM_MODELS


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class ModelTest(BaseModel):
    model: str | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value):
        if value is not None and value not in ALLOWED_LLM_MODELS:
            raise ValueError("不支持该模型")
        return value


class ConversationEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class Favorite(Question):
    pass


class WorkbenchSettingsEdit(BaseModel):
    """用户可以修改的工作台设置；未提交的字段保持原值。"""

    welcome_enabled: bool | None = None
    welcome_title: str | None = Field(default=None, min_length=1, max_length=100)
    welcome_message: str | None = Field(default=None, min_length=1, max_length=500)
    starter_questions: list[str] | None = None
    suggestions_enabled: bool | None = None
    common_questions_enabled: bool | None = None
    common_question_threshold: int | None = Field(default=None, ge=1, le=100)
    llm_model: str | None = None

    @field_validator("welcome_title", "welcome_message")
    @classmethod
    def strip_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("内容不能为空")
        return value.strip() if value is not None else value

    @field_validator("starter_questions")
    @classmethod
    def validate_starter_questions(cls, value):
        if value is None:
            return value
        cleaned = [question.strip() for question in value if question.strip()]
        if len(cleaned) > 10:
            raise ValueError("开场问题最多十条")
        if any(len(question) > 1000 for question in cleaned):
            raise ValueError("单条开场问题不能超过一千字")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("开场问题不能重复")
        return cleaned

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value):
        if value is not None and value not in ALLOWED_LLM_MODELS:
            raise ValueError("不支持该模型")
        return value


class Feedback(BaseModel):
    message_id: str
    comment: str = Field(min_length=1, max_length=1000)


class FeedbackReview(BaseModel):
    """回复校对更新项；处理状态只允许待处理和已处理。"""

    status: str
    resolution_note: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"pending", "resolved"}:
            raise ValueError("不支持的反馈状态")
        return value
