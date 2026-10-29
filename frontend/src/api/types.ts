export interface Me {
  user: { id: number; username: string; name: string; email: string; phone: string; is_platform_admin: boolean };
  schools: { id: number; name: string; code: string }[];
  school: {
    id: number;
    name: string;
    short_name: string;
    code: string;
    location: string;
    motto: string;
    logo: string | null;
    other_income_enabled: boolean;
  } | null;
  roles: { role: string; label: string; scope_type: string; scope_id: number | null }[];
  perms: string[];
  modules: string[];
  module_labels: Record<string, string>;
  access: "full" | "read_only" | "suspended" | null;
  approval_level: number;
  /** Authority over accounts: 0 general staff … 100 director, 101 platform team / super admin. */
  rank: number;
  is_superuser: boolean;
  /** Which door this session came in by. Platform rights exist only in "platform". */
  portal: "school" | "platform";
}

export interface RoleInfo {
  value: string;
  label: string;
  rank: number;
  description: string;
  perms: string[];
  assignable: boolean;
}

export interface Option {
  value: string;
  label: string;
}

export interface Term {
  id: number;
  academic_year: number;
  number: number;
  label: string;
  start_date: string;
  end_date: string;
  status: string;
  next_term_begins: string | null;
}

export interface SchoolClass {
  id: number;
  section: number;
  section_name: string;
  rule_set: string;
  level: string;
  name: string;
  class_teacher_name?: string | null;
  deputy_class_teacher_name?: string | null;
  order: number;
  is_candidate_class: boolean;
  next_class: number | null;
  streams: { id: number; name: string; label: string; school_class: number }[];
}

export interface LearnerRow {
  id: number;
  adm_no: string;
  lin: string;
  full_name: string;
  first_name: string;
  last_name: string;
  sex: string;
  status: string;
  residence: string;
  medical_flag: string | null;
  photo: string | null;
  current_class: { class_name: string; stream_name: string | null; class_id: number } | null;
}
