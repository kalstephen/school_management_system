import { Center, Loader } from "@mantine/core";
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router";

import { useAuth } from "./auth/AuthContext";
import { AppLayout } from "./layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { VerifyPage } from "./pages/VerifyPage";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LearnersPage = lazy(() => import("./pages/learners/LearnersPage"));
const LearnerProfilePage = lazy(() => import("./pages/learners/LearnerProfilePage"));
const AdmissionsPage = lazy(() => import("./pages/learners/AdmissionsPage"));
const RollCallPage = lazy(() => import("./pages/attendance/RollCallPage"));
const AttendanceReportsPage = lazy(() => import("./pages/attendance/AttendanceReportsPage"));
const DisciplinePage = lazy(() => import("./pages/learners/DisciplinePage"));
const TimetablePage = lazy(() => import("./pages/academics/TimetablePage"));
const ExamsPage = lazy(() => import("./pages/academics/ExamsPage"));
const MarkSheetsPage = lazy(() => import("./pages/academics/MarkSheetsPage"));
const MarkEntryPage = lazy(() => import("./pages/academics/MarkEntryPage"));
const ReportCardsPage = lazy(() => import("./pages/academics/ReportCardsPage"));
const PromotionPage = lazy(() => import("./pages/academics/PromotionPage"));
const CurriculumPage = lazy(() => import("./pages/academics/CurriculumPage"));
const HistoryPage = lazy(() => import("./pages/academics/HistoryPage"));
const UnebPage = lazy(() => import("./pages/academics/UnebPage"));
const AnalyticsPage = lazy(() => import("./pages/academics/AnalyticsPage"));
const StaffPage = lazy(() => import("./pages/StaffPage"));
const LibraryPage = lazy(() => import("./pages/operations/LibraryPage"));
const SickbayPage = lazy(() => import("./pages/operations/SickbayPage"));
const StoresPage = lazy(() => import("./pages/operations/StoresPage"));
const FinanceOverviewPage = lazy(() => import("./pages/finance/FinanceOverviewPage"));
const ExpensesPage = lazy(() => import("./pages/finance/ExpensesPage"));
const RequisitionsPage = lazy(() => import("./pages/finance/RequisitionsPage"));
const NoticesPage = lazy(() => import("./pages/NoticesPage"));
const PlannerPage = lazy(() => import("./pages/PlannerPage"));
const SetupPage = lazy(() => import("./pages/admin/SetupPage"));
const UsersPage = lazy(() => import("./pages/admin/UsersPage"));
const AuditPage = lazy(() => import("./pages/admin/AuditPage"));
const PlatformPage = lazy(() => import("./pages/admin/PlatformPage"));
const PlatformSetupPage = lazy(() => import("./pages/admin/PlatformSetupPage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
const LandingPage = lazy(() => import("./pages/public/LandingPage"));
const JoinPage = lazy(() => import("./pages/public/JoinPage"));

function Loading() {
  return (
    <Center h="60vh">
      <Loader />
    </Center>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!me) {
    // Visitors who are not signed in see the SPEX School Manager home page first.
    if (location.pathname === "/") return <Navigate to="/home" replace />;
    const door = location.pathname.startsWith("/platform") ? "/platform/login" : "/login";
    return <Navigate to={door} replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

const page = (element: ReactNode) => <Suspense fallback={<Loading />}>{element}</Suspense>;

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage portal="school" /> },
  { path: "/platform/login", element: <LoginPage portal="platform" /> },
  { path: "/verify/:token", element: <VerifyPage /> },
  { path: "/home", element: page(<LandingPage />) },
  { path: "/join", element: page(<JoinPage />) },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: page(<DashboardPage />) },
      { path: "learners", element: page(<LearnersPage />) },
      { path: "learners/:id", element: page(<LearnerProfilePage />) },
      { path: "admissions", element: page(<AdmissionsPage />) },
      { path: "attendance", element: page(<RollCallPage />) },
      { path: "attendance/reports", element: page(<AttendanceReportsPage />) },
      { path: "discipline", element: page(<DisciplinePage />) },
      { path: "timetable", element: page(<TimetablePage />) },
      { path: "exams", element: page(<ExamsPage />) },
      { path: "marks", element: page(<MarkSheetsPage />) },
      { path: "marks/:id", element: page(<MarkEntryPage />) },
      { path: "report-cards", element: page(<ReportCardsPage />) },
      { path: "promotion", element: page(<PromotionPage />) },
      { path: "curriculum", element: page(<CurriculumPage />) },
      { path: "history", element: page(<HistoryPage />) },
      { path: "uneb", element: page(<UnebPage />) },
      { path: "analytics", element: page(<AnalyticsPage />) },
      { path: "staff", element: page(<StaffPage />) },
      { path: "library", element: page(<LibraryPage />) },
      { path: "sickbay", element: page(<SickbayPage />) },
      { path: "stores", element: page(<StoresPage />) },
      { path: "finance", element: page(<FinanceOverviewPage />) },
      { path: "finance/expenses", element: page(<ExpensesPage />) },
      { path: "finance/requisitions", element: page(<RequisitionsPage />) },
      { path: "notices", element: page(<NoticesPage />) },
      { path: "planner", element: page(<PlannerPage />) },
      { path: "setup", element: page(<SetupPage />) },
      { path: "users", element: page(<UsersPage />) },
      { path: "audit", element: page(<AuditPage />) },
      { path: "platform", element: page(<PlatformPage />) },
      { path: "platform/schools/:id/setup", element: page(<PlatformSetupPage />) },
      { path: "account", element: page(<AccountPage />) },
      { path: "*", element: page(<NotFoundPage />) },
    ],
  },
]);
