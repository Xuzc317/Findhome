"""HouseSearch Local v1 - 后端包

统一导入约定：所有模块一律使用 `from backend.xxx import yyy` 绝对导入，
因此必须在项目根目录（本包的上一级）作为工作目录或加入 sys.path 后运行。

    正确: cd HouseSearch-local-v1 && uvicorn backend.main:app
    错误: cd HouseSearch-local-v1/backend && uvicorn main:app
"""

__version__ = "1.0.0"
