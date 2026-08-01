export interface User {
  id: number;
  tg_id: number;
  username: string | null;
  nickname: string;
  role: 'artist' | 'customer';
  bio: string | null;
  completed_orders_count: number;
  rating: number;
  is_available: boolean;
  profile_visible: boolean;
  created_at: string;
}

export interface PortfolioItem {
  id: number;
  artist_id: number;
  title: string;
  description: string | null;
  display_order: number;
  file_id: string | null;
  file_url?: string;
  created_at: string;
}

export interface ProfileData {
  user: User;
  portfolio: PortfolioItem[];
  is_owner: boolean;
}
