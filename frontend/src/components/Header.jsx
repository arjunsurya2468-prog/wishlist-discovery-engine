import React from 'react';
import { ArrowLeft, Edit3, ShoppingBag } from 'lucide-react';

export default function Header({ title, subtitle, itemCount }) {
  return (
    <div className="header">
      <button className="icon-button">
        <ArrowLeft size={28} />
      </button>
      <div className="header-title-group">
        <div className="header-title">{title}</div>
        <div className="header-subtitle">{subtitle}</div>
      </div>
      <div className="header-actions">
        <button className="icon-button">
          <Edit3 size={28} />
        </button>
        <div className="header-icon-container">
          <button className="icon-button">
            <ShoppingBag size={28} />
          </button>
          <div className="badge">{itemCount}</div>
        </div>
      </div>
    </div>
  );
}
