import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FiX, FiTrash2, FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import type { PortfolioItem } from '../../types';
import './Lightbox.css';

interface LightboxProps {
  item: PortfolioItem | null;
  isOwner: boolean;
  onClose: () => void;
  onDelete?: (item: PortfolioItem) => void;
  onPrev?: () => void;
  onNext?: () => void;
}

export const Lightbox: React.FC<LightboxProps> = ({ item, isOwner, onClose, onDelete, onPrev, onNext }) => {
  return (
    <AnimatePresence>
      {item && (
        <motion.div
          className="lightbox-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="lightbox-content"
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.92 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            onClick={(event) => event.stopPropagation()}
          >
            <button className="lightbox-close" onClick={onClose} aria-label="Закрыть">
              <FiX size={20} />
            </button>

            {onPrev && (
              <button className="lightbox-nav lightbox-nav-prev" onClick={onPrev} aria-label="Предыдущая">
                <FiChevronLeft size={22} />
              </button>
            )}
            {onNext && (
              <button className="lightbox-nav lightbox-nav-next" onClick={onNext} aria-label="Следующая">
                <FiChevronRight size={22} />
              </button>
            )}

            {item.file_url && <img className="lightbox-image" src={item.file_url} alt={item.title} />}

            <div className="lightbox-info">
              <h3 className="lightbox-title">{item.title}</h3>
              {item.description && <p className="lightbox-description">{item.description}</p>}
              {isOwner && onDelete && (
                <button className="lightbox-delete" onClick={() => onDelete(item)}>
                  <FiTrash2 size={16} />
                  Удалить работу
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
