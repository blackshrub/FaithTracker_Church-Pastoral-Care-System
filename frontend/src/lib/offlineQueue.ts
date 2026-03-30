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

/** Input for enqueuing a new operation */
export interface QueuedOperationInput {
  type: string;
  payload?: Record<string, unknown>;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  optimisticUpdate?: Record<string, unknown>;
}

type OperationStatus = 'pending' | 'completed' | 'failed' | 'permanently_failed';

/** A queued operation stored in IndexedDB */
export interface QueuedOperation extends QueuedOperationInput {
  id: number;
  createdAt: string;
  updatedAt?: string;
  status: OperationStatus;
  retryCount: number;
  lastError: string | null;
}

/** Result of a sync attempt */
export interface SyncResult {
  synced: number;
  failed: number;
}

/** Queue statistics */
export interface QueueStats {
  total: number;
  pending: number;
  failed: number;
  completed: number;
}

type QueueChangeListener = () => void;

/** Executor function type for custom sync logic */
type OperationExecutor = (operation: QueuedOperation) => Promise<unknown>;

const DB_NAME = 'faithtracker-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending-operations';

/**
 * Open IndexedDB database
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db = (event.target as IDBOpenDBRequest).result;

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
  private db: IDBDatabase | null;
  private isOnline: boolean;
  private syncInProgress: boolean;
  private listeners: Set<QueueChangeListener>;

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
  async init(): Promise<IDBDatabase> {
    if (!this.db) {
      this.db = await openDB();
    }
    return this.db;
  }

  /**
   * Add a listener for queue changes
   */
  subscribe(callback: QueueChangeListener): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Notify all listeners of queue changes
   */
  private notify(): void {
    this.listeners.forEach((callback) => callback());
  }

  /**
   * Enqueue an operation for later sync
   */
  async enqueue(operation: QueuedOperationInput): Promise<QueuedOperation> {
    const db = await this.init();

    const queuedOperation = {
      ...operation,
      createdAt: new Date().toISOString(),
      status: 'pending' as const,
      retryCount: 0,
      lastError: null,
    };

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add(queuedOperation);

      request.onsuccess = () => {
        this.notify();
        resolve({ ...queuedOperation, id: request.result as number });
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all pending operations
   */
  async getPending(): Promise<QueuedOperation[]> {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const index = store.index('status');
      const request = index.getAll('pending');

      request.onsuccess = () => resolve(request.result as QueuedOperation[]);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get queue statistics
   */
  async getStats(): Promise<QueueStats> {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => {
        const operations = request.result as QueuedOperation[];
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
  async updateStatus(id: number, status: OperationStatus, error: string | null = null): Promise<QueuedOperation | null> {
    const db = await this.init();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const getRequest = store.get(id);

      getRequest.onsuccess = () => {
        const operation = getRequest.result as QueuedOperation | undefined;
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
  async cleanup(maxAgeMs: number = 24 * 60 * 60 * 1000): Promise<number> {
    const db = await this.init();
    const cutoff = new Date(Date.now() - maxAgeMs).toISOString();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => {
        const operations = request.result as QueuedOperation[];
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
   * @param executor - Function to execute the operation (default: fetch API)
   */
  async sync(executor: OperationExecutor | null = null): Promise<SyncResult> {
    if (!this.isOnline || this.syncInProgress) {
      return { synced: 0, failed: 0 };
    }

    this.syncInProgress = true;
    let synced = 0;
    let failed = 0;

    try {
      const pending = await this.getPending();

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
          const errorMessage = error instanceof Error ? error.message : String(error);
          await this.updateStatus(operation.id, 'failed', errorMessage);

          // If max retries exceeded, mark as permanently failed
          if (operation.retryCount >= 3) {
            await this.updateStatus(operation.id, 'permanently_failed', errorMessage);
          }
          failed++;
        }
      }

      // Clean up old completed operations
      await this.cleanup();
    } finally {
      this.syncInProgress = false;
      this.notify();
    }

    return { synced, failed };
  }

  /**
   * Execute a single operation using fetch API
   */
  private async executeOperation(operation: QueuedOperation): Promise<unknown> {
    const { endpoint, method, payload } = operation;
    const apiBaseUrl: string = import.meta.env.VITE_API_URL || '/api';
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
      const errorData = await response.json().catch(() => ({})) as Record<string, unknown>;
      throw new Error((errorData.detail as string) || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Clear all operations
   */
  async clear(): Promise<void> {
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
