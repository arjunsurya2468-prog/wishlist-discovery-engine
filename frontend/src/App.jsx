import React, { Component, useCallback, useEffect, useState } from 'react';
import { Battery, Wifi } from 'lucide-react';
import {
  BrowserRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';
import './pdp.css';

// Wishlist Components
import img1 from './assets/black_tshirt.jpg';
import img2 from './assets/navy_tshirt.jpg';
import img3 from './assets/grey_sweatshirt.jpg';
import img4 from './assets/beige_sweatshirt.jpg';
import img5 from './assets/printed_tshirt.jpg';
import img6 from './assets/striped_tshirt.jpg';

import Header from './components/Header';
import LocationBar from './components/LocationBar';
import ActionPills from './components/ActionPills';
import CategoryChips from './components/CategoryChips';
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

const ROUTES = {
  home: '/',
  wishlist: '/wishlist',
  collection: '/collection',
  pdp: '/pdp',
  reviews: '/reviews',
  comparison: '/better-matches',
};

const SCREEN_JUMPS = [
  { label: 'Home', path: ROUTES.home },
  { label: 'Wishlist', path: ROUTES.wishlist },
  { label: 'Collection', path: ROUTES.collection },
  { label: 'PDP', path: ROUTES.pdp },
  { label: 'Reviews', path: ROUTES.reviews },
  { label: 'Better Matches', path: ROUTES.comparison },
];

const PDP_PRODUCTS = {
  'london-hills-henley': {
    id: 'london-hills-henley',
    brand: 'London Hills',
    name: 'Men Henley Neck T-shirt',
    image: img1,
    currentPrice: 393,
    originalPrice: 1299,
    discount: '70% OFF!',
    discountShort: '70% OFF',
    dealPrice: 364,
    extraOff: 29,
    rating: '4.1',
    ratingsCount: 31,
    reviewsCount: 7,
    color: 'Black',
    selectedSize: 'L',
    chest: '42.0in',
    category: 'tshirt',
    productCode: '44164231',
  },
  'london-hills-tshirt': {
    id: 'london-hills-tshirt',
    brand: 'London Hills',
    name: 'London Hills Men T-shirt',
    image: img1,
    currentPrice: 382,
    originalPrice: 1299,
    discount: '71% OFF!',
    discountShort: '71% OFF',
    dealPrice: 353,
    extraOff: 29,
    rating: '4.1',
    ratingsCount: 31,
    reviewsCount: 7,
    color: 'Black',
    selectedSize: 'L',
    chest: '42.0in',
    category: 'tshirt',
    productCode: '44164232',
  },
  'london-hills-pack-2': {
    id: 'london-hills-pack-2',
    brand: 'London Hills',
    name: 'London Hills Men Pack Of 2 Solid T-shirts',
    image: img1,
    currentPrice: 499,
    originalPrice: 2598,
    discount: '81% OFF!',
    discountShort: '81% OFF',
    dealPrice: 470,
    extraOff: 29,
    rating: '4.0',
    ratingsCount: 44,
    reviewsCount: 9,
    color: 'Black',
    selectedSize: 'L',
    chest: '42.0in',
    category: 'tshirt',
    productCode: '44164233',
  },
  'roadster-grey-sweatshirt': {
    id: 'roadster-grey-sweatshirt',
    brand: 'Roadster',
    name: 'Men Grey Solid Sweatshirt',
    image: img3,
    currentPrice: 650,
    originalPrice: 1300,
    discount: '50% OFF!',
    discountShort: '50% OFF',
    dealPrice: 621,
    extraOff: 29,
    rating: '3.8',
    ratingsCount: 52,
    reviewsCount: 12,
    color: 'Grey',
    selectedSize: 'L',
    chest: '42.0in',
    category: 'sweatshirt',
    productCode: '30981473',
  },
};

const DEFAULT_PDP_PRODUCT = PDP_PRODUCTS['london-hills-henley'];
const NUDGE_PRODUCT = PDP_PRODUCTS['roadster-grey-sweatshirt'];

function productPath(productId) {
  return `${ROUTES.pdp}/${productId}`;
}

const INITIAL_COMPARISONS = [
  {
    id: 1,
    saved: { brand: 'London Hills', name: 'London Hills Men T-shirt', price: 382, score: 3.2, reviews: 4, image: img1 },
    alt: { brand: 'Moda Rapido', name: 'Men Pure Cotton T-shirt', price: 410, mrp: 999, score: 4.6, reviews: 19, image: img2 },
  },
  {
    id: 2,
    saved: { brand: 'Roadster', name: 'Men Grey Solid Sweatshirt', price: 650, score: 3.8, reviews: 12, image: img3 },
    alt: { brand: 'H&M', name: 'Relaxed Fit Sweatshirt', price: 799, score: 4.5, reviews: 34, image: img4 },
  },
  {
    id: 3,
    saved: { brand: 'HERE&NOW', name: 'Men Printed T-shirt', price: 349, score: 3.1, reviews: 8, image: img5 },
    alt: { brand: 'WROGN', name: 'Men Slim Fit Printed T-shirt', price: 549, mrp: 1199, score: 4.4, reviews: 26, image: img6 },
  },
];

const PRODUCTS = [
  { pdpId: 'london-hills-tshirt', brand: 'London Hills', desc: 'London Hills Men T-shirt', currentPrice: 382, discount: '71% OFF', originalPrice: 1299, image: img1 },
  { pdpId: 'london-hills-pack-2', brand: 'London Hills', desc: 'London Hills Men Pack Of 2 Solid...', currentPrice: 499, discount: '81% OFF', originalPrice: 2598, image: img1 },
  { pdpId: 'roadster-grey-sweatshirt', brand: 'Roadster', desc: 'Men Grey Solid Sweatshirt', currentPrice: 650, discount: '50% OFF', originalPrice: 1300, image: img3 },
];

class PhoneErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Phone screen failed to render', error, errorInfo);
    this.props.onError();
  }

  render() {
    if (this.state.hasError) {
      return <RouteRecovery />;
    }

    return this.props.children;
  }
}

function RouteRecovery() {
  return (
    <div className="route-recovery" role="status">
      Returning to Home…
    </div>
  );
}

function InvalidRoute({ onFallback }) {
  useEffect(() => {
    onFallback();
  }, [onFallback]);

  return <RouteRecovery />;
}

function StatusBar() {
  return (
    <div className="phone-status-bar" aria-hidden="true">
      <span className="status-time">9:41</span>
      <div className="status-icons">
        <span className="cellular-bars">
          <i></i><i></i><i></i><i></i>
        </span>
        <Wifi size={15} strokeWidth={2.5} />
        <Battery size={20} strokeWidth={2.25} />
      </div>
    </div>
  );
}

function WishlistScreen({ isCollection = false, comparisons, onBack, onNavigate }) {
  return (
    <>
      <Header
        title={isCollection ? 'To buy' : 'Wishlist'}
        subtitle={isCollection ? '2 items' : '3 items'}
        itemCount={2}
        onBack={onBack}
      />

      <div className="scrollable-content">
        <LocationBar />

        <ActionPills
          isCollection={isCollection}
          matchCount={comparisons.length}
          onCompareClick={() => onNavigate(ROUTES.comparison)}
          onCollectionClick={() => onNavigate(ROUTES.collection)}
        />

        <CategoryChips chips={
          isCollection
            ? [{ label: 'Tshirts' }]
            : [{ label: 'Tshirts' }, { label: 'Sweatshirts' }]
        } />

        <div className="product-grid">
          {PRODUCTS.slice(0, isCollection ? 2 : 3).map((product, index) => (
            <ProductCard
              key={index}
              {...product}
              onView={() => onNavigate(productPath(product.pdpId))}
            />
          ))}
        </div>

        {isCollection ? <QuoteBlock /> : null}
      </div>
    </>
  );
}

function ProductDetailScreen({
  activeConcern,
  setActiveConcern,
  staleItemsCount,
  onBack,
  onWishlist,
  onViewReviews,
}) {
  const { productId } = useParams();
  const product = productId ? PDP_PRODUCTS[productId] : DEFAULT_PDP_PRODUCT;

  if (!product) {
    throw new Error(`Unknown product: ${productId}`);
  }

  return (
    <>
      <HeaderPDP
        staleItemsCount={staleItemsCount}
        onBack={onBack}
        onWishlist={onWishlist}
      />
      <div className="scrollable-content">
        <HeroSection product={product} />
        <DeliverySection product={product} />
        <DetailsSection product={product} />
        <TrustBadges />
        <SimilarProducts />
        <ReviewsSection
          activeConcern={activeConcern}
          setActiveConcern={setActiveConcern}
          onViewAll={onViewReviews}
          product={product}
        />
        <MoreInfo product={product} />
        <Recommendations />
      </div>
    </>
  );
}

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [activeConcern, setActiveConcern] = useState('Fit');
  const [staleItemsCount, setStaleItemsCount] = useState(1);
  const [showWishlistReminder, setShowWishlistReminder] = useState(true);
  const [comparisons, setComparisons] = useState(INITIAL_COMPARISONS);
  const [showFailureToast, setShowFailureToast] = useState(false);

  const goTo = useCallback((path, options) => {
    navigate(path, options);
  }, [navigate]);

  const goBack = useCallback(() => {
    const historyIndex = window.history.state?.idx;

    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1);
      return;
    }

    navigate(ROUTES.home, { replace: true });
  }, [navigate]);

  const handleWishlistClick = useCallback(() => {
    setStaleItemsCount(0);
    navigate(ROUTES.wishlist);
  }, [navigate]);

  const recoverToHome = useCallback(() => {
    setShowFailureToast(true);
    navigate(ROUTES.home, { replace: true });
  }, [navigate]);

  useEffect(() => {
    if (!showFailureToast) return undefined;

    const toastTimer = window.setTimeout(() => {
      setShowFailureToast(false);
    }, 4500);

    return () => window.clearTimeout(toastTimer);
  }, [showFailureToast]);

  const handleDismissComparison = useCallback((id) => {
    setComparisons((currentComparisons) => (
      currentComparisons.filter((comparison) => comparison.id !== id)
    ));
  }, []);

  return (
    <main className="prototype-stage">
      <div className="phone-frame">
        <div className="phone-shell">
          <StatusBar />
          <div className="phone-viewport">
            <div className="mobile-app-container">
              <PhoneErrorBoundary
                key={location.pathname}
                onError={recoverToHome}
              >
                <Routes>
                  <Route
                    path={ROUTES.home}
                    element={(
                      <>
                        <HomePage
                          staleItemsCount={staleItemsCount}
                          onWishlistClick={handleWishlistClick}
                        />
                        {showWishlistReminder && staleItemsCount > 0 ? (
                          <WishlistOverlay
                            product={NUDGE_PRODUCT}
                            onDismiss={() => setShowWishlistReminder(false)}
                            onViewItem={() => {
                              setShowWishlistReminder(false);
                              navigate(productPath(NUDGE_PRODUCT.id));
                            }}
                          />
                        ) : null}
                      </>
                    )}
                  />
                  <Route
                    path={ROUTES.wishlist}
                    element={(
                      <WishlistScreen
                        comparisons={comparisons}
                        onBack={goBack}
                        onNavigate={goTo}
                      />
                    )}
                  />
                  <Route
                    path={ROUTES.collection}
                    element={(
                      <WishlistScreen
                        isCollection
                        comparisons={comparisons}
                        onBack={goBack}
                        onNavigate={goTo}
                      />
                    )}
                  />
                  <Route
                    path={ROUTES.pdp}
                    element={(
                      <ProductDetailScreen
                        activeConcern={activeConcern}
                        setActiveConcern={setActiveConcern}
                        staleItemsCount={staleItemsCount}
                        onBack={goBack}
                        onWishlist={handleWishlistClick}
                        onViewReviews={() => navigate(ROUTES.reviews)}
                      />
                    )}
                  />
                  <Route
                    path={`${ROUTES.pdp}/:productId`}
                    element={(
                      <ProductDetailScreen
                        activeConcern={activeConcern}
                        setActiveConcern={setActiveConcern}
                        staleItemsCount={staleItemsCount}
                        onBack={goBack}
                        onWishlist={handleWishlistClick}
                        onViewReviews={() => navigate(ROUTES.reviews)}
                      />
                    )}
                  />
                  <Route
                    path={ROUTES.reviews}
                    element={(
                      <div className="scrollable-content">
                        <ReviewsPage
                          activeConcern={activeConcern}
                          setActiveConcern={setActiveConcern}
                          onBack={goBack}
                        />
                      </div>
                    )}
                  />
                  <Route
                    path={ROUTES.comparison}
                    element={(
                      <div className="scrollable-content">
                        <ComparisonPage
                          comparisons={comparisons}
                          onDismissItem={handleDismissComparison}
                          onBack={goBack}
                          onViewProduct={() => navigate(ROUTES.pdp)}
                          onViewReviews={() => navigate(ROUTES.reviews)}
                        />
                      </div>
                    )}
                  />
                  <Route
                    path="*"
                    element={<InvalidRoute onFallback={recoverToHome} />}
                  />
                </Routes>
              </PhoneErrorBoundary>
            </div>
          </div>
        </div>
      </div>

      <nav className="screen-jump-strip" aria-label="Demo screen shortcuts">
        {SCREEN_JUMPS.map((screen) => (
          <button
            key={screen.path}
            type="button"
            className={
              location.pathname === screen.path
              || (screen.path === ROUTES.pdp && location.pathname.startsWith(`${ROUTES.pdp}/`))
                ? 'active'
                : ''
            }
            onClick={() => navigate(screen.path, { replace: true })}
            aria-current={
              location.pathname === screen.path
              || (screen.path === ROUTES.pdp && location.pathname.startsWith(`${ROUTES.pdp}/`))
                ? 'page'
                : undefined
            }
          >
            {screen.label}
          </button>
        ))}
      </nav>

      <div
        className={`screen-failure-toast ${showFailureToast ? 'visible' : ''}`}
        role="status"
        aria-live="polite"
      >
        Screen failed to load — returned to Home.
      </div>
    </main>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
