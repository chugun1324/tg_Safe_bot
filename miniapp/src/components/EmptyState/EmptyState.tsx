import React from 'react';
import { motion } from 'framer-motion';
import { FiEdit3 } from 'react-icons/fi';
import './EmptyState.css';

interface EmptyStateProps {
  onStart: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onStart }) => {
  return (
    <motion.div
      className="empty-state"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="empty-state-icon">✨</div>
      <h2 className="empty-state-title">Заполните профиль</h2>
      <p className="empty-state-text">
        Расскажите о себе и добавьте работы в портфолио — так заказчики увидят, чем вы занимаетесь,
        ещё до первого сообщения.
      </p>
      <motion.button className="empty-state-cta" onClick={onStart} whileTap={{ scale: 0.96 }}>
        <FiEdit3 size={16} />
        Создать профиль
      </motion.button>
    </motion.div>
  );
};
