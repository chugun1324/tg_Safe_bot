import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ProfileHeader } from '../components/ProfileHeader/ProfileHeader';
import { EditProfileForm } from '../components/EditProfileForm/EditProfileForm';
import { PortfolioGrid } from '../components/PortfolioGrid/PortfolioGrid';
import { Lightbox } from '../components/Lightbox/Lightbox';
import { UploadModal } from '../components/UploadModal/UploadModal';
import { EmptyState } from '../components/EmptyState/EmptyState';
import { useProfileStore } from '../stores/profileStore';
import { profileService } from '../services/api';
import type { PortfolioItem } from '../types';
import './ProfilePage.css';

export const ProfilePage: React.FC = () => {
  const { profile, updateUser, addPortfolioItem, deletePortfolioItem, reorderPortfolio } = useProfileStore();
  const [editing, setEditing] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  if (!profile) return null;

  const { user, is_owner: isOwner } = profile;
  const isArtist = user.role === 'artist';
  const sortedPortfolio = [...profile.portfolio].sort((a, b) => a.display_order - b.display_order);
  const isEmpty = isOwner && isArtist && !user.bio && sortedPortfolio.length === 0;

  const handleMove = async (item: PortfolioItem, direction: 'up' | 'down') => {
    const idx = sortedPortfolio.findIndex((entry) => entry.id === item.id);
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (idx === -1 || swapIdx < 0 || swapIdx >= sortedPortfolio.length) return;

    const other = sortedPortfolio[swapIdx];
    const itemOrder = item.display_order;
    const otherOrder = other.display_order;

    const reordered = sortedPortfolio
      .map((entry) => {
        if (entry.id === item.id) return { ...entry, display_order: otherOrder };
        if (entry.id === other.id) return { ...entry, display_order: itemOrder };
        return entry;
      })
      .sort((a, b) => a.display_order - b.display_order);

    reorderPortfolio(reordered);
    try {
      await Promise.all([
        profileService.reorderPortfolio(item.id, otherOrder),
        profileService.reorderPortfolio(other.id, itemOrder),
      ]);
    } catch {
      // Best-effort — a stale order self-heals on next load.
    }
  };

  const handleDelete = async (item: PortfolioItem) => {
    deletePortfolioItem(item.id);
    setLightboxIndex(null);
    try {
      await profileService.deletePortfolioItem(item.id);
    } catch {
      // Best-effort.
    }
  };

  const activeItem = lightboxIndex != null ? sortedPortfolio[lightboxIndex] ?? null : null;

  return (
    <div className="profile-page">
      <ProfileHeader user={user} isOwner={isOwner} onEditClick={() => setEditing((value) => !value)} />

      <AnimatePresence>
        {editing && (
          <EditProfileForm
            user={user}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => {
              updateUser(updated);
              setEditing(false);
            }}
          />
        )}
      </AnimatePresence>

      {isEmpty && !editing && <EmptyState onStart={() => setEditing(true)} />}

      {isArtist && (
        <>
          <div className="profile-section-title">Портфолио</div>
          {sortedPortfolio.length === 0 && !isOwner ? (
            <div className="profile-portfolio-empty">У исполнителя пока нет работ в портфолио</div>
          ) : (
            <PortfolioGrid
              items={sortedPortfolio}
              isOwner={isOwner}
              onItemClick={(item) => setLightboxIndex(sortedPortfolio.findIndex((entry) => entry.id === item.id))}
              onAddClick={isOwner ? () => setUploadOpen(true) : undefined}
              onMove={isOwner ? handleMove : undefined}
            />
          )}
        </>
      )}

      <Lightbox
        item={activeItem}
        isOwner={isOwner}
        onClose={() => setLightboxIndex(null)}
        onDelete={isOwner ? handleDelete : undefined}
        onPrev={
          lightboxIndex != null && lightboxIndex > 0 ? () => setLightboxIndex((idx) => (idx ?? 0) - 1) : undefined
        }
        onNext={
          lightboxIndex != null && lightboxIndex < sortedPortfolio.length - 1
            ? () => setLightboxIndex((idx) => (idx ?? 0) + 1)
            : undefined
        }
      />

      {isOwner && (
        <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={addPortfolioItem} />
      )}
    </div>
  );
};
