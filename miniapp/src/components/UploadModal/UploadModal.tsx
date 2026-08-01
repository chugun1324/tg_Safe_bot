import React, { useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FiX, FiImage } from 'react-icons/fi';
import { profileService } from '../../services/api';
import type { PortfolioItem } from '../../types';
import './UploadModal.css';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUploaded: (item: PortfolioItem) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({ open, onClose, onUploaded }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setFile(null);
    setPreviewUrl(null);
    setTitle('');
    setDescription('');
    setError(null);
    setSubmitting(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null;
    setFile(picked);
    setPreviewUrl(picked ? URL.createObjectURL(picked) : null);
  };

  const handleSubmit = async () => {
    if (!file) {
      setError('Выберите изображение');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('title', title.trim() || 'Без названия');
      if (description.trim()) formData.append('description', description.trim());
      const item = await profileService.addPortfolioItem(formData);
      onUploaded(item);
      handleClose();
    } catch {
      setError('Не удалось загрузить работу. Попробуйте ещё раз.');
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="upload-modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
        >
          <motion.div
            className="upload-modal"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 40 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="upload-modal-header">
              <h3>Новая работа</h3>
              <button className="upload-modal-close" onClick={handleClose} aria-label="Закрыть">
                <FiX size={20} />
              </button>
            </div>

            <button
              type="button"
              className="upload-modal-dropzone"
              onClick={() => fileInputRef.current?.click()}
              style={previewUrl ? { backgroundImage: `url(${previewUrl})` } : undefined}
            >
              {!previewUrl && (
                <>
                  <FiImage size={28} />
                  <span>Выбрать изображение</span>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={handleFileChange}
            />

            <input
              className="upload-modal-input"
              placeholder="Название работы"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={255}
            />
            <textarea
              className="upload-modal-textarea"
              placeholder="Описание (необязательно)"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={1000}
              rows={3}
            />

            {error && <div className="upload-modal-error">{error}</div>}

            <button className="upload-modal-submit" onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Загрузка…' : 'Добавить в портфолио'}
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
