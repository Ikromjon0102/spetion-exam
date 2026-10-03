import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useLanguage } from "../i18n/LanguageContext";
import ClassLoginPage from "../features/student/ClassLoginPage";
const ExamListPage = lazy(() => import("../features/student/ExamListPage"));
const ExamTakingPage = lazy(() => import("../features/student/ExamTakingPage"));
const ExamResultPage = lazy(() => import("../features/student/ExamResultPage"));
const ProfilePage = lazy(() => import("../features/student/ProfilePage"));
const StaffLoginPage = lazy(() => import("../features/admin/StaffLoginPage"));
const DashboardPage = lazy(() => import("../features/admin/DashboardPage"));
const AdminExamListPage = lazy(() => import("../features/admin/ExamListPage"));
const ExamUploadPage = lazy(() => import("../features/admin/ExamUploadPage"));
const ExamReviewEditor = lazy(() => import("../features/admin/ExamReviewEditor"));
const RankingPage = lazy(() => import("../features/admin/RankingPage"));
const AttemptAnswerReviewPage = lazy(() => import("../features/admin/AttemptAnswerReviewPage"));
const OverallRankingPage = lazy(() => import("../features/admin/OverallRankingPage"));
const StudentPerformancePage = lazy(() => import("../features/admin/StudentPerformancePage"));
const DailyResultsPage = lazy(() => import("../features/admin/DailyResultsPage"));
const ChangePasswordPage = lazy(() => import("../features/shared/ChangePasswordPage"));
const ClassesPage = lazy(() => import("../features/admin/manage/ClassesPage"));
const ClassDetailPage = lazy(() => import("../features/admin/manage/ClassDetailPage"));
const SubjectsPage = lazy(() => import("../features/admin/manage/SubjectsPage"));
const StudentsPage = lazy(() => import("../features/admin/manage/StudentsPage"));
const TeachersPage = lazy(() => import("../features/admin/manage/TeachersPage"));
import RequireRole from "../auth/RequireRole";

function RouteFallback() {
  const { t } = useLanguage();
  return (
    <div className="page">
      <p className="ink-muted">{t("taking.loading")}</p>
    </div>
  );
}

// Every page except the student login is loaded on demand. The whole app used
// to ship as one ~580 kB script, so a student opening the login page also
// downloaded the admin panel, the chart code and the image exporter — on a
// phone connection that is seconds of "Yuklanmoqda..." before anything shows.
export default function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
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
          path="/admin/exams/:examId/attempts/:studentId/review"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <AttemptAnswerReviewPage />
            </RequireRole>
          }
        />

        <Route
          path="/ranking"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <OverallRankingPage />
            </RequireRole>
          }
        />
        <Route
          path="/students/:studentId/performance"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <StudentPerformancePage />
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
          path="/classes/:classId/daily-results"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <DailyResultsPage />
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
      </Suspense>
    </BrowserRouter>
  );
}
