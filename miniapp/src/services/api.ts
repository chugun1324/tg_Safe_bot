import axios from 'axios';
import type { User, PortfolioItem, ProfileData } from '../types';

// Empty by default: requests go out as relative paths (/api/..., /media/...),
// which vite.config.ts proxies to the bot's aiohttp server in dev, and which
// resolve same-origin when the built app is served behind the same domain/reverse
// proxy as the API in production.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add Telegram Web App init data to all requests
api.interceptors.request.use((config) => {
  const initData = window.Telegram?.WebApp?.initData;
  if (initData) {
    config.headers['X-Telegram-Init-Data'] = initData;
  }
  return config;
});

export const profileService = {
  async getProfile(tgId: number): Promise<ProfileData> {
    const response = await api.get(`/api/profile/${tgId}`);
    return response.data;
  },

  async updateProfile(data: { nickname?: string; bio?: string | null }): Promise<User> {
    const response = await api.put('/api/profile/me', data);
    return response.data;
  },

  async addPortfolioItem(formData: FormData): Promise<PortfolioItem> {
    const response = await api.post('/api/portfolio', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async updatePortfolioItem(itemId: number, data: Partial<PortfolioItem>): Promise<PortfolioItem> {
    const response = await api.patch(`/api/portfolio/${itemId}`, data);
    return response.data;
  },

  async deletePortfolioItem(itemId: number): Promise<void> {
    await api.delete(`/api/portfolio/${itemId}`);
  },

  async reorderPortfolio(itemId: number, newOrder: number): Promise<void> {
    await api.patch(`/api/portfolio/${itemId}/reorder`, { display_order: newOrder });
  },
};
