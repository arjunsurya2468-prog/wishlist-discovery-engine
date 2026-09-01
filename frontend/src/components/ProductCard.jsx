import React from 'react';
import { ShoppingBag, Trash2, FolderPlus, Share2 } from 'lucide-react';

export default function ProductCard({ brand, desc, currentPrice, discount, originalPrice, image, onView }) {
  return (
    <div className="product-card" onClick={onView}>
      <div className="product-image-container">
        {image ? (
          <img src={image} alt={desc} className="product-placeholder" style={{objectFit: 'contain', width: '100%', height: '100%'}} />
        ) : (
          <div className="product-placeholder"></div>
        )}
        <button className="add-button" onClick={(event) => event.stopPropagation()}>
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
        <button className="action-bar-btn" onClick={(event) => event.stopPropagation()}><Trash2 size={20} /></button>
        <button className="action-bar-btn" onClick={(event) => event.stopPropagation()}><FolderPlus size={20} /></button>
        <button className="action-bar-btn" onClick={(event) => event.stopPropagation()}><Share2 size={20} /></button>
      </div>
    </div>
  );
}
