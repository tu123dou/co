"""HTTP 依赖声明。"""

from typing import Annotated

from fastapi import Depends

from ..auth import current_user

User = Annotated[dict, Depends(current_user)]
