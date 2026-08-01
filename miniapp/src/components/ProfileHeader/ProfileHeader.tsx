import React from 'react';
import { motion } from 'framer-motion';
import { FiUser, FiCheckCircle, FiEdit2 } from 'react-icons/fi';
import type { User } from '../../types';
import { RatingGauge } from '../RatingGauge/RatingGauge';
import './ProfileHeader.css';

interface ProfileHeaderProps {
  user: User;
  isOwner: boolean;
  onEditClick?: () => void;
}

const ROLE_LABELS: Record<User['role'], string> = {
  artist: '🎨 Исполнитель',
  customer: '🧑‍💼 Заказчик',
};

export const ProfileHeader: React.FC<ProfileHeaderProps> = ({ user, isOwner, onEditClick }) => {
  const avatarLetters = user.nickname?.substring(0, 2).toUpperCase() || 'US';
  const roleLabel = ROLE_LABELS[user.role] ?? user.role;

  return (
    <motion.div
      className="profile-header"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="profile-header-bg">
        <div className="gradient-overlay" />
      </div>

      <div className="profile-header-content">
        <div className="profile-avatar-wrapper">
          <motion.div
            className="profile-avatar"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <FiUser size={48} />
            <div className="avatar-letters">{avatarLetters}</div>
          </motion.div>

          {user.is_available && (
            <motion.div
              className="availability-badge"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.3 }}
            >
              <span className="status-dot" />
            </motion.div>
          )}
        </div>

        <div className="profile-info">
          <div className="profile-name-row">
            <h1 className="profile-name">{user.nickname}</h1>
            {isOwner && (
              <motion.button
                className="edit-button"
                onClick={onEditClick}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
              >
                <FiEdit2 size={18} />
              </motion.button>
            )}
          </div>

          <div className="profile-meta-row">
            {user.username && <p className="profile-username">@{user.username}</p>}
            <span className="profile-role-badge">{roleLabel}</span>
          </div>

          {user.bio && (
            <motion.p
              className="profile-bio"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              {user.bio}
            </motion.p>
          )}
        </div>

        <div className="profile-stats">
          <motion.div
            className="stat-item"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
          >
            <FiCheckCircle className="stat-icon" />
            <div className="stat-content">
              <span className="stat-value">{user.completed_orders_count}</span>
              <span className="stat-label">Заказов</span>
            </div>
          </motion.div>

          {user.rating > 0 && (
            <motion.div
              className="stat-item stat-item-rating"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4 }}
            >
              <RatingGauge rating={user.rating} />
              <span className="stat-label">Рейтинг</span>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
};
