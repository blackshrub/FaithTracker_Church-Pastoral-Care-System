// Gesture Support and Touch Optimizations
class GestureManager {
  constructor() {
    this.touchStart = { x: 0, y: 0, time: 0 };
    this.swipeThreshold = 100;
    this.timeThreshold = 300;
  }

  // Initialize touch handlers
  init(element) {
    element.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: true });
    element.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: true });
    element.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: true });
  }

  handleTouchStart(e) {
    this.touchStart = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      time: new Date().getTime()
    };
  }

  handleTouchMove(e) {
    // Smooth scroll optimizations
    e.target.style.scrollBehavior = 'smooth';
  }

  handleTouchEnd(e) {
    const touchEnd = {
      x: e.changedTouches[0].clientX,
      y: e.changedTouches[0].clientY,
      time: new Date().getTime()
    };

    const deltaX = touchEnd.x - this.touchStart.x;
    const deltaY = touchEnd.y - this.touchStart.y;
    const deltaTime = touchEnd.time - this.touchStart.time;

    // Swipe gestures
    if (Math.abs(deltaX) > this.swipeThreshold && deltaTime < this.timeThreshold) {
      if (deltaX > 0) {
        this.onSwipeRight();
      } else {
        this.onSwipeLeft();
      }
    }

    // Double tap for quick actions
    if (deltaTime < 300 && Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) {
      this.handleDoubleTap(e);
    }
  }

  onSwipeRight() {
    // Navigate back or close modals
    if (window.history.length > 1) {
      window.history.back();
    }
  }

  onSwipeLeft() {
    // Quick actions menu
    this.showQuickActions();
  }

  handleDoubleTap(e) {
    // Quick member contact for member rows
    const memberRow = e.target.closest('[data-member-id]');
    if (memberRow) {
      const memberId = memberRow.getAttribute('data-member-id');
      const phone = memberRow.getAttribute('data-member-phone');
      if (phone) {
        window.open(`https://wa.me/${phone.replace(/^0/, '62')}`, '_blank');
      }
    }
  }

  showQuickActions() {
    // Show floating action buttons
    const quickActionEvent = new CustomEvent('showQuickActions');
    document.dispatchEvent(quickActionEvent);
  }
}

// Biometric Authentication Manager
class BiometricAuth {
  constructor() {
    this.isSupported = 'credentials' in navigator && 'PublicKeyCredential' in window;
  }

  async isAvailable() {
    if (!this.isSupported) return false;
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  }

  async register(userId, userName) {
    if (!await this.isAvailable()) {
      throw new Error('Biometric authentication not available');
    }

    try {
      const credential = await navigator.credentials.create({
        publicKey: {
          challenge: new Uint8Array(32),
          rp: { name: 'GKBJ Pastoral Care' },
          user: {
            id: new TextEncoder().encode(userId),
            name: userName,
            displayName: userName
          },
          pubKeyCredParams: [{ alg: -7, type: 'public-key' }],
          authenticatorSelection: {
            authenticatorAttachment: 'platform',
            userVerification: 'required'
          }
        }
      });

      // Store credential ID for future authentication
      localStorage.setItem('biometric_credential_id', credential.id);
      return credential;
    } catch (error) {
      console.error('Biometric registration failed:', error);
      throw error;
    }
  }

  async authenticate() {
    if (!await this.isAvailable()) {
      throw new Error('Biometric authentication not available');
    }

    const credentialId = localStorage.getItem('biometric_credential_id');
    if (!credentialId) {
      throw new Error('No biometric credentials registered');
    }

    try {
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge: new Uint8Array(32),
          allowCredentials: [{
            id: new TextEncoder().encode(credentialId),
            type: 'public-key'
          }],
          userVerification: 'required'
        }
      });

      return credential;
    } catch (error) {
      console.error('Biometric authentication failed:', error);
      throw error;
    }
  }
}

// Touch optimization utilities
export const TouchOptimizer = {
  // Smooth scroll with momentum
  enableSmoothScrolling(element) {
    element.style.webkitOverflowScrolling = 'touch';
    element.style.scrollBehavior = 'smooth';
  },

  // Optimize tap delays
  enableFastTap(element) {
    element.addEventListener('touchstart', () => {}, { passive: true });
    element.style.touchAction = 'manipulation';
  },

  // Prevent zoom on input focus
  preventZoomOnFocus() {
    const meta = document.querySelector('meta[name="viewport"]');
    if (meta) {
      meta.content = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no';
    }
  }
};

export const gestureManager = new GestureManager();
export const biometricAuth = new BiometricAuth();