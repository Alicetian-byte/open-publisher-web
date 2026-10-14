export interface Project {
  id: string;
  name: string;
  description: string;
  website_url: string | null;
  github_url: string | null;
  target_audience: string;
  selling_points: string[];
  goals: string;
  tone: string;
  platforms: string[];
  status: string;
  created_at: string;
  updated_at: string;
}
