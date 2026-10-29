import {
  IconBook2,
  IconBooks,
  IconBuildingStore,
  IconCalendarStats,
  IconCash,
  IconChartBar,
  IconCheckupList,
  IconClipboardCheck,
  IconClipboardList,
  IconFileCertificate,
  IconFirstAidKit,
  IconGavel,
  IconHistory,
  IconLayoutDashboard,
  IconListCheck,
  IconNotebook,
  IconReceipt2,
  IconReportAnalytics,
  IconSchool,
  IconSettings,
  IconSpeakerphone,
  IconStairsUp,
  IconTimeline,
  IconUserPlus,
  IconUsers,
  IconUsersGroup,
  IconWorld,
} from "@tabler/icons-react";
import type { ReactNode } from "react";

export interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
  perm?: string;
  anyPerm?: string[];
  module?: string;
  platformOnly?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

const size = 18;

export const NAVIGATION: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", path: "/", icon: <IconLayoutDashboard size={size} />, perm: "dashboard.view" },
      { label: "My planner", path: "/planner", icon: <IconNotebook size={size} />, perm: "dashboard.view" },
      { label: "Analytics", path: "/analytics", icon: <IconChartBar size={size} />, perm: "assessment.view", module: "assessment" },
    ],
  },
  {
    label: "Learners",
    items: [
      { label: "Learners", path: "/learners", icon: <IconUsers size={size} />, perm: "learners.view", module: "learners" },
      { label: "Admissions", path: "/admissions", icon: <IconUserPlus size={size} />, perm: "admissions.view", module: "admissions" },
      { label: "Roll call", path: "/attendance", icon: <IconClipboardCheck size={size} />, perm: "attendance.take", module: "attendance" },
      { label: "Attendance reports", path: "/attendance/reports", icon: <IconCalendarStats size={size} />, perm: "attendance.view", module: "attendance" },
      { label: "Discipline & welfare", path: "/discipline", icon: <IconGavel size={size} />, perm: "discipline.view", module: "discipline" },
    ],
  },
  {
    label: "Academics",
    items: [
      { label: "Curriculum", path: "/curriculum", icon: <IconBook2 size={size} />, perm: "curriculum.view", module: "curriculum" },
      { label: "Timetable", path: "/timetable", icon: <IconCalendarStats size={size} />, perm: "timetable.view", module: "timetable" },
      { label: "Exams", path: "/exams", icon: <IconClipboardList size={size} />, perm: "assessment.view", module: "assessment" },
      { label: "Mark sheets", path: "/marks", icon: <IconListCheck size={size} />, perm: "assessment.view", module: "assessment" },
      { label: "Report cards", path: "/report-cards", icon: <IconFileCertificate size={size} />, perm: "reports.view", module: "assessment" },
      { label: "Performance history", path: "/history", icon: <IconTimeline size={size} />, perm: "assessment.view", module: "assessment" },
      { label: "Promotion", path: "/promotion", icon: <IconStairsUp size={size} />, perm: "promotion.view", module: "promotion" },
      { label: "UNEB results", path: "/uneb", icon: <IconReportAnalytics size={size} />, perm: "assessment.view", module: "assessment" },
    ],
  },
  {
    label: "People",
    items: [
      { label: "Staff & HR", path: "/staff", icon: <IconUsersGroup size={size} />, perm: "dashboard.view", module: "staff" },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Library", path: "/library", icon: <IconBooks size={size} />, perm: "library.view", module: "library" },
      { label: "Sickbay", path: "/sickbay", icon: <IconFirstAidKit size={size} />, perm: "health.view", module: "sickbay" },
      { label: "Stores & assets", path: "/stores", icon: <IconBuildingStore size={size} />, perm: "stores.view", module: "stores" },
    ],
  },
  {
    label: "Finance",
    items: [
      { label: "Finance overview", path: "/finance", icon: <IconCash size={size} />, perm: "finance.view", module: "finance" },
      { label: "Expenses", path: "/finance/expenses", icon: <IconReceipt2 size={size} />, perm: "finance.view", module: "finance" },
      { label: "Requisitions", path: "/finance/requisitions", icon: <IconCheckupList size={size} />, perm: "finance.request", module: "finance" },
    ],
  },
  {
    label: "Communication",
    items: [
      { label: "Notices", path: "/notices", icon: <IconSpeakerphone size={size} />, perm: "communication.view", module: "communication" },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "School setup", path: "/setup", icon: <IconSchool size={size} />, perm: "setup.view" },
      { label: "Users & roles", path: "/users", icon: <IconSettings size={size} />, perm: "users.manage" },
      { label: "Audit log", path: "/audit", icon: <IconHistory size={size} />, perm: "audit.view" },
      { label: "Owner console", path: "/platform", icon: <IconWorld size={size} />, platformOnly: true },
    ],
  },
];

export function visibleNavigation(can: (p: string) => boolean, has: (m: string) => boolean, isPlatform: boolean): NavGroup[] {
  return NAVIGATION.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      if (item.platformOnly) return isPlatform;
      if (item.module && !has(item.module)) return false;
      if (item.anyPerm) return item.anyPerm.some(can);
      return !item.perm || can(item.perm);
    }),
  })).filter((group) => group.items.length > 0);
}
