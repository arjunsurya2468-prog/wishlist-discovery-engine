import React, { useState } from 'react';
import './pdp.css';

// Wishlist Components
import Header from './components/Header';
import LocationBar from './components/LocationBar';
import ActionPills from './components/ActionPills';
import CategoryChips from './components/CategoryChips';
import PromoBanner from './components/PromoBanner';
import ProductCard from './components/ProductCard';
import QuoteBlock from './components/QuoteBlock';

// PDP Components
import HeaderPDP from './components/pdp/HeaderPDP';
import HeroSection from './components/pdp/HeroSection';
import DeliverySection from './components/pdp/DeliverySection';
import DetailsSection from './components/pdp/DetailsSection';
import TrustBadges from './components/pdp/TrustBadges';
import SimilarProducts from './components/pdp/SimilarProducts';
import ReviewsSection from './components/pdp/ReviewsSection';
import MoreInfo from './components/pdp/MoreInfo';
import Recommendations from './components/pdp/Recommendations';

import ReviewsPage from './components/reviews/ReviewsPage';
import ComparisonPage from './components/comparison/ComparisonPage';
import HomePage from './components/home/HomePage';
import WishlistOverlay from './components/home/WishlistOverlay';

function App() {
  const [screen, setScreen] = useState(6); // Default to new Home Page view
  const [activeConcern, setActiveConcern] = useState('Fit'); // Shared concern state
  
  // Re-engagement states
  const [staleItemsCount, setStaleItemsCount] = useState(1);
  const [showWishlistReminder, setShowWishlistReminder] = useState(true);

  const [comparisons, setComparisons] = useState([
    {
      id: 1,
      saved: { brand: 'London Hills', name: 'London Hills Men T-shirt', price: 382, score: 3.2, reviews: 4 },
      alt: { brand: 'Moda Rapido', name: 'Men Pure Cotton T-shirt', price: 410, mrp: 999, score: 4.6, reviews: 19 }
    },
    {
      id: 2,
      saved: { brand: 'Roadster', name: 'Men Grey Solid Sweatshirt', price: 650, score: 3.8, reviews: 12 },
      alt: { brand: 'H&M', name: 'Relaxed Fit Sweatshirt', price: 799, score: 4.5, reviews: 34 }
    },
    {
      id: 3,
      saved: { brand: 'HERE&NOW', name: 'Men Printed T-shirt', price: 349, score: 3.1, reviews: 8 },
      alt: { brand: 'WROGN', name: 'Men Slim Fit Printed T-shirt', price: 549, mrp: 1199, score: 4.4, reviews: 26 }
    }
  ]);

  const handleDismissComparison = (id) => {
    setComparisons(comparisons.filter(c => c.id !== id));
  };

  const handleWishlistClick = () => {
    setStaleItemsCount(0); // Clear badge
    setScreen(1); // Go to wishlist
  };

  const products = [
    { brand: 'London Hills', desc: 'London Hills Men T-shirt', currentPrice: 382, discount: '71% OFF', originalPrice: 1299 },
    { brand: 'London Hills', desc: 'London Hills Men Pack Of 2 Solid...', currentPrice: 499, discount: '81% OFF', originalPrice: 2598 },
    { brand: 'Roadster', desc: 'Men Grey Solid Sweatshirt', currentPrice: 650, discount: '50% OFF', originalPrice: 1300 },
  ];

  return (
    <>
      <div className="app-controls">
        <button onClick={() => setScreen(1)} style={{ fontWeight: screen === 1 ? 'bold' : 'normal' }}>Screen 1 (Wishlist Main)</button>
        <button onClick={() => setScreen(2)} style={{ fontWeight: screen === 2 ? 'bold' : 'normal' }}>Screen 2 (Collection)</button>
        <button onClick={() => setScreen(3)} style={{ fontWeight: screen === 3 ? 'bold' : 'normal' }}>Screen 3 (PDP)</button>
        <button onClick={() => setScreen(4)} style={{ fontWeight: screen === 4 ? 'bold' : 'normal' }}>Screen 4 (All Reviews)</button>
        <button onClick={() => setScreen(5)} style={{ fontWeight: screen === 5 ? 'bold' : 'normal' }}>Screen 5 (Comparison)</button>
        <button onClick={() => setScreen(6)} style={{ fontWeight: screen === 6 ? 'bold' : 'normal' }}>Screen 6 (Home Feed)</button>
      </div>

      <div className="mobile-app-container">
        {screen === 6 ? (
          <>
            <HomePage 
              staleItemsCount={staleItemsCount}
              onWishlistClick={handleWishlistClick}
            />
            {showWishlistReminder && staleItemsCount > 0 && (
              <WishlistOverlay 
                onDismiss={() => setShowWishlistReminder(false)}
                onViewItem={() => {
                  setShowWishlistReminder(false);
                  setScreen(3);
                }}
                onSeeAlternatives={() => {
                  setShowWishlistReminder(false);
                  setScreen(5);
                }}
              />
            )}
          </>
        ) : screen === 5 ? (
          <div className="scrollable-content">
             <ComparisonPage 
                comparisons={comparisons}
                onDismissItem={handleDismissComparison}
                onBack={() => setScreen(1)}
             />
          </div>
        ) : screen === 4 ? (
          <div className="scrollable-content">
             <ReviewsPage activeConcern={activeConcern} setActiveConcern={setActiveConcern} onBack={() => setScreen(3)} />
          </div>
        ) : screen === 3 ? (
          <>
            <HeaderPDP staleItemsCount={staleItemsCount} />
            <div className="scrollable-content">
              <HeroSection />
              <DeliverySection />
              <DetailsSection />
              <TrustBadges />
              <SimilarProducts />
              <ReviewsSection 
                activeConcern={activeConcern} 
                setActiveConcern={setActiveConcern} 
                onViewAll={() => setScreen(4)} 
              />
              <MoreInfo />
              <Recommendations />
            </div>
          </>
        ) : (
          <>
            <Header 
              title={screen === 1 ? "Wishlist" : "To buy"} 
              subtitle={screen === 1 ? "3 items" : "2 items"} 
              itemCount={2} 
            />
            
            <div className="scrollable-content">
              <LocationBar />
              
              {screen === 1 && (
                <ActionPills 
                  matchCount={comparisons.length} 
                  onCompareClick={() => setScreen(5)} 
                />
              )}
              
              <CategoryChips chips={
                screen === 1 
                  ? [{ label: 'Tshirts' }, { label: 'Sweatshirts' }]
                  : [{ label: 'Tshirts' }]
              } />
              
              <PromoBanner type={screen === 1 ? 'price-drop' : 'low-stock'} />
              
              <div className="product-grid">
                {products.slice(0, screen === 1 ? 3 : 2).map((p, i) => (
                  <ProductCard key={i} {...p} />
                ))}
              </div>
              
              {screen === 2 && <QuoteBlock />}
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default App;
