import React from 'react';
import { ShoppingBag, Trash2, FolderPlus, Share2 } from 'lucide-react';

export default function ProductCard({ brand, desc, currentPrice, discount, originalPrice }) {
  return (
    <div className="product-card">
      <div className="product-image-container">
        <div className="product-placeholder"></div>
        <button className="add-button">
          <ShoppingBag size={16} />
          Add
        </button>
      </div>
      <div className="product-info">
        <div className="product-brand">{brand}</div>
        <div className="product-desc">{desc}</div>
        <div className="product-price-row">
          <span className="price-current">₹{currentPrice}</span>
          <span className="price-discount">{discount}</span>
          <span className="price-original">₹{originalPrice}</span>
        </div>
      </div>
      <div className="action-bar">
        <button className="action-bar-btn"><Trash2 size={20} /></button>
        <button className="action-bar-btn"><FolderPlus size={20} /></button>
        <button className="action-bar-btn"><Share2 size={20} /></button>
      </div>
    </div>
  );
}
