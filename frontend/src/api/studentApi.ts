import { apiClient } from "./client";

export interface ExamListItem {
  id: number;
  title: string;
  subject_name: string;
  start_at: string | null;
  end_at: string | null;
  duration_minutes: number;
  window_state: "upcoming" | "active" | "closed";
  my_attempt_status: string | null;
}

export interface AttemptOption {
  id: number;
  order_index: number;
  option_text: string;
}

export interface AttemptQuestion {
  id: number;
  order_index: number;
  question_type: string;
  prompt_text: string;
  prompt_image_key: string | null;
  points: number;
  options: AttemptOption[];
  selected_option_id: number | null;
  answer_text: string | null;
}

export interface AttemptState {
  attempt_id: number;
  exam_id: number;
  exam_title: string;
  deadline_at: string;
  duration_minutes: number;
  questions: AttemptQuestion[];
}

export interface SubmitResult {
  score: number;
  max_score: number;
  submitted_at: string;
}

export interface ResultQuestion {
  question_id: number;
  prompt_text: string;
  points: number;
  selected_option_id: number | null;
  correct_option_id: number | null;
  is_correct: boolean | null;
  points_awarded: number | null;
}

export interface ExamResult {
  exam_id: number;
  exam_title: string;
  score: number;
  max_score: number;
  percent: number;
  questions: ResultQuestion[];
}

export interface RankingEntry {
  rank_in_class: number;
  student_id: number;
  full_name: string;
  score: number;
  is_me: boolean;
}

export interface SubjectHistoryPoint {
  exam_id: number;
  exam_title: string;
  score: number;
  max_score: number;
  date: string;
}

export interface SubjectHistory {
  subject_id: number;
  subject_name: string;
  exams_taken_count: number;
  average_percent: number | null;
  trend: "improving" | "declining" | "stable" | null;
  timeline: SubjectHistoryPoint[];
}

export interface Subject {
  id: number;
  name: string;
  code: string | null;
}

export async function listSubjects(): Promise<Subject[]> {
  const { data } = await apiClient.get<Subject[]>("/student/subjects");
  return data;
}

export async function listMyExams(): Promise<ExamListItem[]> {
  const { data } = await apiClient.get<ExamListItem[]>("/student/me/exams");
  return data;
}

export async function startExam(examId: number): Promise<AttemptState> {
  const { data } = await apiClient.post<AttemptState>(`/student/exams/${examId}/start`);
  return data;
}

export async function getMyAttempt(examId: number): Promise<AttemptState> {
  const { data } = await apiClient.get<AttemptState>(`/student/exams/${examId}/attempt`);
  return data;
}

export async function submitAnswer(
  examId: number,
  questionId: number,
  body: { selected_option_id?: number | null; answer_text?: string | null }
): Promise<void> {
  await apiClient.put(`/student/exams/${examId}/answers/${questionId}`, body);
}

export async function submitExam(examId: number): Promise<SubmitResult> {
  const { data } = await apiClient.post<SubmitResult>(`/student/exams/${examId}/submit`);
  return data;
}

export async function getResult(examId: number): Promise<ExamResult> {
  const { data } = await apiClient.get<ExamResult>(`/student/exams/${examId}/result`);
  return data;
}

export async function getExamRanking(examId: number): Promise<RankingEntry[]> {
  const { data } = await apiClient.get<RankingEntry[]>(`/student/exams/${examId}/ranking`);
  return data;
}

export async function getSubjectHistory(subjectId: number): Promise<SubjectHistory> {
  const { data } = await apiClient.get<SubjectHistory>(`/student/me/subjects/${subjectId}/history`);
  return data;
}
