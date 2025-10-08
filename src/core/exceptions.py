"""
自定义异常定义
定义评论系统的异常层次结构
"""


class CommentSystemError(Exception):
    """评论系统基础异常类"""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(CommentSystemError):
    """配置错误"""
    pass


class AccountAPIError(CommentSystemError):
    """账号API调用失败"""
    pass


class AccountReservationError(AccountAPIError):
    """账号预留失败"""
    pass


class ContentGenerationError(CommentSystemError):
    """内容生成失败"""
    pass


class ContentValidationError(CommentSystemError):
    """内容验证失败"""
    pass


class RedditPublishError(CommentSystemError):
    """Reddit发布失败"""
    pass


class RateLimitError(CommentSystemError):
    """频率限制错误"""
    pass


class DiscoveryError(CommentSystemError):
    """帖子发现错误"""
    pass


class ScreeningError(CommentSystemError):
    """帖子筛选错误"""
    pass
