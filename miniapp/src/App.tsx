import { useEffect, useState } from 'react';
import { useTelegramWebApp } from './hooks/useTelegramWebApp';
import { useProfileStore } from './stores/profileStore';
import { profileService } from './services/api';
import { ProfilePage } from './pages/ProfilePage';
import './App.css';

function getProfileIdFromUrl(): number | null {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('profile_id');
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

function App() {
  const { isReady, user } = useTelegramWebApp();
  const { profile, loading, error, setProfile, setLoading, setError } = useProfileStore();
  const [targetId, setTargetId] = useState<number | null>(null);

  useEffect(() => {
    if (!isReady) return;
    setTargetId(getProfileIdFromUrl() ?? user?.id ?? null);
  }, [isReady, user]);

  useEffect(() => {
    if (targetId == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    profileService
      .getProfile(targetId)
      .then((data) => {
        if (!cancelled) setProfile(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.status === 404 ? 'not_found' : 'load_failed');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [targetId, setProfile, setLoading, setError]);

  if (!isReady || targetId == null || loading) {
    return (
      <div className="app-shell">
        <div className="skeleton-header" />
        <div className="skeleton-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="skeleton-tile" key={index} />
          ))}
        </div>
      </div>
    );
  }

  if (error === 'not_found') {
    return (
      <div className="app-state">
        <div className="app-state-icon">🔍</div>
        <div className="app-state-title">Профиль не найден</div>
        <div className="app-state-text">Похоже, этот пользователь ещё не зарегистрирован в боте.</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-state">
        <div className="app-state-icon">⚠️</div>
        <div className="app-state-title">Не удалось загрузить профиль</div>
        <div className="app-state-text">Проверьте соединение и откройте профиль ещё раз из бота.</div>
      </div>
    );
  }

  if (!profile) {
    return null;
  }

  return <ProfilePage />;
}

export default App;
