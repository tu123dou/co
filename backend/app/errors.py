"""应用错误不依赖 HTTP；状态码由 API 适配层映射。"""


class ResourceNotFound(Exception):
    pass


class ServiceUnavailable(Exception):
    pass


class QueryBusy(Exception):
    pass


class Forbidden(Exception):
    pass


class InvalidRequest(Exception):
    pass
