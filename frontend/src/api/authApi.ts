import { apiClient } from "./client";

export interface ClassOut {
  id: number;
  display_name: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface MeOut {
  id: number;
  username: string;
  full_name: string;
  role: "student" | "teacher" | "admin";
  homeroom_class_ids: number[];
}

export async function listClasses(): Promise<ClassOut[]> {
  const { data } = await apiClient.get<ClassOut[]>("/auth/classes");
  return data;
}

export async function login(username: string, password: string, classId?: number): Promise<TokenPair> {
  const { data } = await apiClient.post<TokenPair>("/auth/login", {
    username,
    password,
    class_id: classId,
  });
  return data;
}

export async function me(): Promise<MeOut> {
  const { data } = await apiClient.get<MeOut>("/auth/me");
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
