export type SessionUser = {
  id: number;
  name: string;
  email: string;
  timezone: string;
};

export type RegisterInput = {
  name: string;
  email: string;
  password: string;
  timezone?: string;
};

export type LoginInput = {
  email: string;
  password: string;
};
