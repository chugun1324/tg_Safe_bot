import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { profileService } from '../../services/api';
import type { User } from '../../types';
import './EditProfileForm.css';

interface EditProfileFormProps {
  user: User;
  onSaved: (user: User) => void;
  onCancel: () => void;
}

export const EditProfileForm: React.FC<EditProfileFormProps> = ({ user, onSaved, onCancel }) => {
  const [nickname, setNickname] = useState(user.nickname);
  const [bio, setBio] = useState(user.bio ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!nickname.trim()) {
      setError('Ник не может быть пустым');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await profileService.updateProfile({
        nickname: nickname.trim(),
        bio: bio.trim() ? bio.trim() : null,
      });
      onSaved(updated);
    } catch {
      setError('Не удалось сохранить. Попробуйте ещё раз.');
      setSaving(false);
    }
  };

  return (
    <motion.div
      className="edit-profile-form"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
    >
      <label className="edit-profile-label">Ник</label>
      <input
        className="edit-profile-input"
        value={nickname}
        onChange={(event) => setNickname(event.target.value)}
        maxLength={64}
        placeholder="Ваш ник"
      />

      <label className="edit-profile-label">О себе</label>
      <textarea
        className="edit-profile-textarea"
        value={bio}
        onChange={(event) => setBio(event.target.value)}
        maxLength={500}
        rows={4}
        placeholder="Расскажите о себе и своих работах…"
      />
      <span className="edit-profile-counter">{bio.length}/500</span>

      {error && <div className="edit-profile-error">{error}</div>}

      <div className="edit-profile-actions">
        <button className="edit-profile-cancel" onClick={onCancel} disabled={saving}>
          Отмена
        </button>
        <button className="edit-profile-save" onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>
    </motion.div>
  );
};
