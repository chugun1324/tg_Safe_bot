import { useEffect, useState } from 'react';

const WebApp = window.Telegram?.WebApp;

export const useTelegramWebApp = () => {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Outside a real Telegram client (plain browser) window.Telegram is
    // undefined entirely — guard each call so that doesn't crash the app.
    WebApp?.ready();
    WebApp?.expand();
    WebApp?.enableClosingConfirmation();
    WebApp?.setHeaderColor('#0f1729');
    WebApp?.setBackgroundColor('#0f1729');

    setIsReady(true);

    return () => {
      WebApp?.disableClosingConfirmation();
    };
  }, []);

  return {
    isReady,
    webApp: WebApp,
    user: WebApp?.initDataUnsafe?.user,
    themeParams: WebApp?.themeParams,
  };
};
