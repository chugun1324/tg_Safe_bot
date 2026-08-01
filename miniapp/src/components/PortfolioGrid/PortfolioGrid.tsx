import React from 'react';
import { motion } from 'framer-motion';
import { FiPlus, FiArrowUp, FiArrowDown } from 'react-icons/fi';
import type { PortfolioItem } from '../../types';
import './PortfolioGrid.css';

interface PortfolioGridProps {
  items: PortfolioItem[];
  isOwner: boolean;
  onItemClick: (item: PortfolioItem) => void;
  onAddClick?: () => void;
  onMove?: (item: PortfolioItem, direction: 'up' | 'down') => void;
}

export const PortfolioGrid: React.FC<PortfolioGridProps> = ({ items, isOwner, onItemClick, onAddClick, onMove }) => {
  return (
    <div className="portfolio-grid">
      {isOwner && onAddClick && (
        <motion.button
          className="portfolio-tile portfolio-add-tile"
          onClick={onAddClick}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          whileTap={{ scale: 0.97 }}
        >
          <FiPlus size={26} />
          <span>Добавить работу</span>
        </motion.button>
      )}

      {items.map((item, index) => (
        <motion.div
          key={item.id}
          className="portfolio-tile"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.04 * index }}
          whileTap={{ scale: 0.97 }}
          onClick={() => onItemClick(item)}
        >
          {item.file_url ? (
            <img src={item.file_url} alt={item.title} loading="lazy" />
          ) : (
            <div className="portfolio-tile-placeholder" />
          )}
          <div className="portfolio-tile-overlay">
            <span className="portfolio-tile-title">{item.title}</span>
          </div>

          {isOwner && onMove && (
            <div className="portfolio-tile-controls" onClick={(event) => event.stopPropagation()}>
              <button onClick={() => onMove(item, 'up')} aria-label="Переместить выше">
                <FiArrowUp size={14} />
              </button>
              <button onClick={() => onMove(item, 'down')} aria-label="Переместить ниже">
                <FiArrowDown size={14} />
              </button>
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
};
