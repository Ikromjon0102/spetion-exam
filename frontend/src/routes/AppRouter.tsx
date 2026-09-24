import { BrowserRouter, Route, Routes } from "react-router-dom";
import ClassLoginPage from "../features/student/ClassLoginPage";
import ExamListPage from "../features/student/ExamListPage";
import ExamTakingPage from "../features/student/ExamTakingPage";
import ExamResultPage from "../features/student/ExamResultPage";
import ProfilePage from "../features/student/ProfilePage";
import StaffLoginPage from "../features/admin/StaffLoginPage";
import DashboardPage from "../features/admin/DashboardPage";
import AdminExamListPage from "../features/admin/ExamListPage";
import ExamUploadPage from "../features/admin/ExamUploadPage";
import ExamReviewEditor from "../features/admin/ExamReviewEditor";
import RankingPage from "../features/admin/RankingPage";
import ChangePasswordPage from "../features/shared/ChangePasswordPage";
import ClassesPage from "../features/admin/manage/ClassesPage";
import ClassDetailPage from "../features/admin/manage/ClassDetailPage";
import SubjectsPage from "../features/admin/manage/SubjectsPage";
import StudentsPage from "../features/admin/manage/StudentsPage";
import TeachersPage from "../features/admin/manage/TeachersPage";
import RequireRole from "../auth/RequireRole";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ClassLoginPage />} />
        <Route path="/staff-login" element={<StaffLoginPage />} />

        <Route
          path="/change-password"
          element={
            <RequireRole roles={["student", "teacher", "admin"]}>
              <ChangePasswordPage />
            </RequireRole>
          }
        />

        <Route
          path="/student/exams"
          element={
            <RequireRole roles={["student"]}>
              <ExamListPage />
            </RequireRole>
          }
        />
        <Route
          path="/student/exams/:examId"
          element={
            <RequireRole roles={["student"]}>
              <ExamTakingPage />
            </RequireRole>
          }
        />
        <Route
          path="/student/exams/:examId/result"
          element={
            <RequireRole roles={["student"]}>
              <ExamResultPage />
            </RequireRole>
          }
        />
        <Route
          path="/student/profile"
          element={
            <RequireRole roles={["student"]}>
              <ProfilePage />
            </RequireRole>
          }
        />

        <Route
          path="/admin/dashboard"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <DashboardPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/exams"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <AdminExamListPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/exams/upload"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <ExamUploadPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/exams/:examId/review"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <ExamReviewEditor />
            </RequireRole>
          }
        />
        <Route
          path="/admin/exams/:examId/ranking"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <RankingPage />
            </RequireRole>
          }
        />

        <Route
          path="/classes"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <ClassesPage />
            </RequireRole>
          }
        />
        <Route
          path="/classes/:classId"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <ClassDetailPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/manage/subjects"
          element={
            <RequireRole roles={["admin"]}>
              <SubjectsPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/manage/students"
          element={
            <RequireRole roles={["admin"]}>
              <StudentsPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/manage/teachers"
          element={
            <RequireRole roles={["admin"]}>
              <TeachersPage />
            </RequireRole>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
