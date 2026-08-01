import { create } from 'zustand';
import type { ProfileData, User, PortfolioItem } from '../types';

interface ProfileStore {
  profile: ProfileData | null;
  loading: boolean;
  error: string | null;
  setProfile: (profile: ProfileData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  updateUser: (user: Partial<User>) => void;
  addPortfolioItem: (item: PortfolioItem) => void;
  updatePortfolioItem: (itemId: number, data: Partial<PortfolioItem>) => void;
  deletePortfolioItem: (itemId: number) => void;
  reorderPortfolio: (items: PortfolioItem[]) => void;
}

export const useProfileStore = create<ProfileStore>((set) => ({
  profile: null,
  loading: false,
  error: null,

  setProfile: (profile) => set({ profile, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  updateUser: (userData) =>
    set((state) => ({
      profile: state.profile
        ? {
            ...state.profile,
            user: { ...state.profile.user, ...userData },
          }
        : null,
    })),

  addPortfolioItem: (item) =>
    set((state) => ({
      profile: state.profile
        ? {
            ...state.profile,
            portfolio: [...state.profile.portfolio, item],
          }
        : null,
    })),

  updatePortfolioItem: (itemId, data) =>
    set((state) => ({
      profile: state.profile
        ? {
            ...state.profile,
            portfolio: state.profile.portfolio.map((item) =>
              item.id === itemId ? { ...item, ...data } : item
            ),
          }
        : null,
    })),

  deletePortfolioItem: (itemId) =>
    set((state) => ({
      profile: state.profile
        ? {
            ...state.profile,
            portfolio: state.profile.portfolio.filter((item) => item.id !== itemId),
          }
        : null,
    })),

  reorderPortfolio: (items) =>
    set((state) => ({
      profile: state.profile
        ? {
            ...state.profile,
            portfolio: items,
          }
        : null,
    })),
}));
