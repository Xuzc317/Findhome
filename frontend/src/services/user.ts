import BaseService from "./base";


export default class UserService extends BaseService {
  login(params: {
    userName: string;
    password: string;
  }) {
    return this.post<LoginRes>("/v1/user-account/login", params);
  }

  register(params: {
    email: string,
    password: string,
    inviteCode?: string
  }) {
    return this.post("/v1/user-account/mail-register", params)
  }

  activate(params: {
    activationCode: string;
  }) {
    return this.post("/v1/user-account/activate", params);
  }

  reActivate(params: {
    email: string
  }) {
    return this.post("/v1/user-account/re-activate", params)
  }

  findPasswordCode(params: {
    email: string;
  }) {
    return this.post("/v1/user-account/find-password-code", params)
  }

  resetPassword(params: {
    password: string;
    resetCode: string;
  }) {
    return this.post("/v1/user-account/reset-password", params)
  }

  getUserInfo(skipTokenError?: boolean) {
    return this.get<UserInfo>("/v1/user/info", {}, skipTokenError);
  }

}