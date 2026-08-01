import React from 'react';
import { motion } from 'framer-motion';
import './RatingGauge.css';

interface RatingGaugeProps {
  rating: number; // 0-100
}

const SIZE = 76;
const STROKE = 8;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export const RatingGauge: React.FC<RatingGaugeProps> = ({ rating }) => {
  const clamped = Math.max(0, Math.min(100, rating));
  const offset = CIRCUMFERENCE * (1 - clamped / 100);

  return (
    <div className="rating-gauge">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--border-color)"
          strokeWidth={STROKE}
        />
        <motion.circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="url(#rating-gradient)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          initial={{ strokeDashoffset: CIRCUMFERENCE }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
        />
        <defs>
          <linearGradient id="rating-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7c6dfc" />
            <stop offset="100%" stopColor="#ff5ea8" />
          </linearGradient>
        </defs>
      </svg>
      <div className="rating-gauge-value">
        <span className="rating-gauge-number">{clamped}</span>
        <span className="rating-gauge-max">/100</span>
      </div>
    </div>
  );
};
