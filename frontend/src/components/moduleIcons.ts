import {
  IconBooks,
  IconBuildingStore,
  IconCalendarStats,
  IconCash,
  IconClipboardCheck,
  IconFileCertificate,
  IconFirstAidKit,
  IconGavel,
  IconSchool,
  IconSpeakerphone,
  IconStairsUp,
  IconUserPlus,
  IconUsers,
  IconUsersGroup,
  IconBook2,
  type Icon,
} from "@tabler/icons-react";

/** One icon, colour and screen per module, shared by the tick lists and the dashboard tiles. */
export const MODULE_META: Record<string, { icon: Icon; color: string; path: string }> = {
  setup: { icon: IconSchool, color: "indigo", path: "/setup" },
  admissions: { icon: IconUserPlus, color: "cyan", path: "/admissions" },
  learners: { icon: IconUsers, color: "blue", path: "/learners" },
  staff: { icon: IconUsersGroup, color: "teal", path: "/staff" },
  curriculum: { icon: IconBook2, color: "violet", path: "/curriculum" },
  timetable: { icon: IconCalendarStats, color: "grape", path: "/timetable" },
  attendance: { icon: IconClipboardCheck, color: "green", path: "/attendance" },
  assessment: { icon: IconFileCertificate, color: "orange", path: "/marks" },
  promotion: { icon: IconStairsUp, color: "lime", path: "/promotion" },
  discipline: { icon: IconGavel, color: "red", path: "/discipline" },
  communication: { icon: IconSpeakerphone, color: "pink", path: "/notices" },
  finance: { icon: IconCash, color: "yellow", path: "/finance" },
  library: { icon: IconBooks, color: "cyan", path: "/library" },
  sickbay: { icon: IconFirstAidKit, color: "red", path: "/sickbay" },
  stores: { icon: IconBuildingStore, color: "orange", path: "/stores" },
};

export function moduleIcon(key: string): Icon {
  return MODULE_META[key]?.icon ?? IconSchool;
}
