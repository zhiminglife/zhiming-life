export type BirthInfo = {
  calendar: "solar" | "lunar";
  year: number;
  month: number;
  day: number;
  hour: number;
  gender: "male" | "female";
  is_leap_month: boolean;
  birth_place: string;
};

export type Person = {
  id: string;
  name: string;
  relationship: string;
  birth: BirthInfo | null;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type Session = {
  id: string;
  primary_person_id: string;
  secondary_person_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

export type ModelSettings = {
  base_url: string;
  model: string;
  has_api_key: boolean;
};

export type LibraryKind = "knowledge" | "cases";

export type LibraryStatus = {
  kind: LibraryKind;
  path: string;
  source_count: number;
  chunk_count: number;
  vector_backend: string;
};

export type LibrarySource = {
  id: string;
  title: string;
  source_name: string;
  chunk_count: number;
  created_at: string;
};

export type Evidence = {
  library_kind: LibraryKind;
  source_id: string;
  source_name: string;
  title: string;
  position: number;
  content: string;
  score: number;
};

export type Chart = {
  year: string;
  month: string;
  day: string;
  hour: string;
  day_master: string;
  day_master_wuxing: string;
  wuxing_counts: Record<string, number>;
  rendered: string;
};
