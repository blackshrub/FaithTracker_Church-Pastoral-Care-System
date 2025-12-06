/**
 * offlineQueue - IndexedDB-backed sync queue for offline operations
 *
 * Provides offline-first capabilities by:
 * - Queuing mutations when offline
 * - Persisting queue to IndexedDB
 * - Auto-syncing when back online
 * - Conflict resolution
 *
 * Usage:
 * import { offlineQueue } from '@/lib/offlineQueue';
 *
 * // Queue an operation
 * await offlineQueue.enqueue({
 *   type: 'COMPLETE_EVENT',
 *   payload: { eventId: '123' },
 *   endpoint: '/care-events/123/complete',
 *   method: 'POST'
 * });
 *
 * // Sync when online
 * await offlineQueue.sync();
 */

const DB_NAME = 'faithtracker-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending-operations';

/**
 * Open IndexedDB database
 */
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      // Create pending operations store
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        });
        store.createIndex('createdAt', 'createdAt', { unique: false });
        store.createIndex('type', 'type', { unique: false });
        store.createIndex('status', 'status', { unique: false });
      }
    };
  });
}

/**
 * Offline Queue Manager
 */
class OfflineQueue {
  constructor() {
    this.db = null;
    this.isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
    this.syncInProgress = false;
    this.listeners = new Set();

    // Listen for online/offline events
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        this.isOnline = true;
        this.sync();
      });
      window.addEventListener('offline', () => {
        this.isOnline = false;
      });
    }
  }

  /**
   * Initialize the database connection
   */
  async init() {
    if (!this.db) {
      this.db = await openDB();
    }
    return this.db;
  }

  /**
   * Add a listener for queue changes
   */
  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Notify all listeners of queue changes
   */
  notify() {
    this.listeners.forEach((callback) => callback());
  }

  /**
   * Enqueue an operation for later sync
   * @param {Object} operation - Operation to queue
   * @param {string} operation.type - Operation type (e.g., 'COMPLETE_EVENT')
   * @param {Object} operation.payload - Operation payload
   * @param {string} operation.endpoint - API endpoint
   * @param {string} operation.method - HTTP method (POST, PUT, DELETE)
   * @param {Object} [operation.optimisticUpdate] - Optional optimistic update config
   */
  async enqueue(operation) {
    const db = await this.init();

    const queuedOperation = {
      ...operation,
      createdAt: new Date().toISOString(),
      status: 'pending',
      retryCount: 0,
      lastError: null,
    };

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add(queuedOperation);

      request.onsuccess = () => {
        this.notify();
        resolve({ ...queuedOperation, id: request.result });
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all pending operations
   */
  async getPending() {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const index = store.index('status');
      const request = index.getAll('pending');

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get queue statistics
   */
  async getStats() {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => {
        const operations = request.result;
        resolve({
          total: operations.length,
          pending: operations.filter((op) => op.status === 'pending').length,
          failed: operations.filter((op) => op.status === 'failed').length,
          completed: operations.filter((op) => op.status === 'completed').length,
        });
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Update operation status
   */
  async updateStatus(id, status, error = null) {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const getRequest = store.get(id);

      getRequest.onsuccess = () => {
        const operation = getRequest.result;
        if (operation) {
          operation.status = status;
          operation.lastError = error;
          operation.retryCount = (operation.retryCount || 0) + (status === 'failed' ? 1 : 0);
          operation.updatedAt = new Date().toISOString();

          const putRequest = store.put(operation);
          putRequest.onsuccess = () => {
            this.notify();
            resolve(operation);
          };
          putRequest.onerror = () => reject(putRequest.error);
        } else {
          resolve(null);
        }
      };
      getRequest.onerror = () => reject(getRequest.error);
    });
  }

  /**
   * Remove completed operations older than specified age
   */
  async cleanup(maxAgeMs = 24 * 60 * 60 * 1000) {
    const db = await this.init();
    const cutoff = new Date(Date.now() - maxAgeMs).toISOString();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => {
        const operations = request.result;
        let deleteCount = 0;

        operations.forEach((op) => {
          if (op.status === 'completed' && op.createdAt < cutoff) {
            store.delete(op.id);
            deleteCount++;
          }
        });

        this.notify();
        resolve(deleteCount);
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Sync all pending operations
   * @param {Function} executor - Function to execute the operation (default: fetch API)
   */
  async sync(executor = null) {
    if (!this.isOnline || this.syncInProgress) {
      return { synced: 0, failed: 0 };
    }

    this.syncInProgress = true;
    const pending = await this.getPending();
    let synced = 0;
    let failed = 0;

    for (const operation of pending) {
      try {
        if (executor) {
          await executor(operation);
        } else {
          await this.executeOperation(operation);
        }
        await this.updateStatus(operation.id, 'completed');
        synced++;
      } catch (error) {
        await this.updateStatus(operation.id, 'failed', error.message);

        // If max retries exceeded, mark as permanently failed
        if (operation.retryCount >= 3) {
          await this.updateStatus(operation.id, 'permanently_failed', error.message);
        }
        failed++;
      }
    }

    this.syncInProgress = false;
    this.notify();

    // Clean up old completed operations
    await this.cleanup();

    return { synced, failed };
  }

  /**
   * Execute a single operation using fetch API
   */
  async executeOperation(operation) {
    const { endpoint, method, payload } = operation;
    const apiBaseUrl = import.meta.env.VITE_API_URL || '/api';
    const token = localStorage.getItem('token');

    const response = await fetch(`${apiBaseUrl}${endpoint}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: payload ? JSON.stringify(payload) : undefined,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Clear all operations
   */
  async clear() {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onsuccess = () => {
        this.notify();
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }
}

// Singleton instance
export const offlineQueue = new OfflineQueue();

export default offlineQueue;
