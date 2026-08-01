// Minimal surface of the official Telegram Mini App SDK (loaded via the
// <script src="https://telegram.org/js/telegram-web-app.js"> tag in
// index.html), covering only what this app actually uses. We use the
// official global instead of @twa-dev/sdk because that package mangles
// non-ASCII characters (e.g. Cyrillic first_name) in initData, which
// silently breaks the backend's HMAC signature check.
interface TelegramWebAppUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramWebAppUser };
  themeParams: TelegramThemeParams;
  ready(): void;
  expand(): void;
  enableClosingConfirmation(): void;
  disableClosingConfirmation(): void;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp;
  };
}
