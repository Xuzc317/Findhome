interface ApiResponse<T> {
  code: number;
  data: T;
}

interface LoginRes {
  token: string;
  user: UserInfo;
}

interface UserInfo {
  checkInRecord?: string;
  createTime: string;
  dataVersion: number;
  id: number;
  inviteCode: string;
  nickName: string;
  operator: string;
  uuid: string;
  updateTime: string;
  userEmail: string;
  userName: string;
  userStatus: string;
}
