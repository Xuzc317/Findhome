
import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import { API_BASE_URL, StorageKey } from "@/constant";
import { getBrowserToken, setBrowserToken } from "@/utils/user";
import { removeLocalStorage } from "@/utils/storage";
export const CODE_ERROR = -99;

export default class BaseService {
  private instance: AxiosInstance;

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000 * 6,
    });

    // 添加请求拦截器
    this.instance.interceptors.request.use(function (config) {
      const token = getBrowserToken();
      // 如果token存在，则将其添加到请求头
      if (token) {
        config.headers["token"] = token;
      }
      return config;
    });
  }

  protected async get<T>(path: string, params?: Params, skipTokenError?: boolean) {
    const res = await this.request<ApiResponse<T>>("GET", path, params, skipTokenError);
    return res.data;
  }

  protected async post<T>(path: string, data?: Params, skipTokenError?: boolean) {
    const res = await this.request<ApiResponse<T>>("POST", path, data, skipTokenError);
    return res.data;
  }

  protected async put<T>(path: string, data: Params, skipTokenError?: boolean) {
    const res = await this.request<ApiResponse<T>>("PUT", path, data, skipTokenError);
    return res.data;
  }

  protected async delete<T>(path: string, data?: Params, skipTokenError?: boolean) {
    const res = await this.request<ApiResponse<T>>("DELETE", path, data, skipTokenError);
    return res.data;
  }

  private request<T>(
    method: "POST" | "GET" | "PUT" | "DELETE",
    path: string,
    params?: Params,
    skipTokenError?: boolean,
  ) {
    const config: AxiosRequestConfig = {
      method: method,
      url: path,
    };
    if (method === "POST" || method === "PUT") {
      config.data = params;
    } else {
      config.params = params;
    }
    return this.instance.request<T>(config).catch((error) => {
      if (
        !skipTokenError &&
        (error.response?.status === 401 || error.response?.status === 403)
      ) {
        setBrowserToken("");
        removeLocalStorage(StorageKey.USER_INFO)
        window.location.href = "/user/login/";
        return Promise.reject(
          new CustomError("您的登录已过期，请重新登录。", CODE_ERROR, 401),
        );
      }
      let message = error.message;
      if (error.response?.data?.error) {
        message = error.response?.data?.error;
      }
      return Promise.reject(
        new CustomError(
          message,
          error.request?.data?.code || CODE_ERROR,
          error.response?.status,
        ),
      );
    });
  }
}

export class CustomError extends Error {
  code?: number;
  status?: number;
  constructor(message: string, code?: number, status?: number) {
    super(message);
    this.code = code;
    this.status = status;
    Object.setPrototypeOf(this, CustomError.prototype);
  }
}


type Params = Record<string, unknown> | unknown[]
