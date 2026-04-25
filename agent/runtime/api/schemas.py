from pydantic import BaseModel


class TaskCommand(BaseModel):
    task: str


class ActionAllowCommand(BaseModel):
    allow_act: bool


class BaseRotateCommand(BaseModel):
    steps: int


class ReconnectCommand(BaseModel):
    force: bool = False
    reason: str | None = None


class ReloadModelCommand(BaseModel):
    checkpoint_path: str
    policy_type: str | None = None