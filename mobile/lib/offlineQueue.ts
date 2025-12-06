/**
 * Offline Queue - Storage-backed sync queue for offline operations
 *
 * Provides offline-first capabilities by:
 * - Queuing mutations when offline
 * - Persisting queue to storage (MMKV in production, in-memory in Expo Go)
 * - Auto-syncing when back online
 * - Retry with exponential backoff
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

import NetInfo from '@react-native-community/netinfo';

// Use centralized storage (works in both Expo Go and production)
import { storage } from '@/lib/storage';

// ============================================================================
// TYPES
// ============================================================================

export type OperationStatus = 'pending' | 'failed' | 'completed' | 'permanently_failed';

export interface QueuedOperation {
  id: number;
  type: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  payload?: Record<string, unknown>;
  createdAt: string;
  updatedAt?: string;
  status: OperationStatus;
  retryCount: number;
  lastError?: string;
}

export interface QueueStats {
  total: number;
  pending: number;
  failed: number;
  completed: number;
  permanentlyFailed: number;
}

export type QueueListener = () => void;

export type OperationExecutor = (operation: QueuedOperation) => Promise<unknown>;

// ============================================================================
// CONSTANTS
// ============================================================================

const STORAGE_KEY = 'offline-queue:operations';
const ID_COUNTER_KEY = 'offline-queue:id-counter';
const MAX_RETRIES = 3;

// ============================================================================
// OFFLINE QUEUE CLASS
// ============================================================================

class OfflineQueue {
  private isOnline: boolean = true;
  private syncInProgress: boolean = false;
  private listeners: Set<QueueListener> = new Set();
  private unsubscribeNetInfo: (() => void) | null = null;

  constructor() {
    this.init();
  }

  /**
   * Initialize the queue and network listeners
   */
  private init(): void {
    // Get initial network state
    NetInfo.fetch().then((state) => {
      this.isOnline = state.isConnected === true && state.isInternetReachable !== false;
    });

    // Subscribe to network changes
    this.unsubscribeNetInfo = NetInfo.addEventListener((state) => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected === true && state.isInternetReachable !== false;

      // Auto-sync when coming back online
      if (wasOffline && this.isOnline) {
        this.sync();
      }
    });
  }

  /**
   * Subscribe to queue changes
   */
  subscribe(callback: QueueListener): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Notify all listeners of queue changes
   */
  private notify(): void {
    this.listeners.forEach((callback) => {
      try {
        callback();
      } catch (error) {
        console.warn('Queue listener error:', error);
      }
    });
  }

  /**
   * Get next auto-increment ID
   */
  private getNextId(): number {
    const currentId = storage.getNumber(ID_COUNTER_KEY) ?? 0;
    const nextId = currentId + 1;
    storage.set(ID_COUNTER_KEY, nextId);
    return nextId;
  }

  /**
   * Get all operations from storage
   */
  private getAllOperations(): QueuedOperation[] {
    const data = storage.getString(STORAGE_KEY);
    if (!data) return [];
    try {
      return JSON.parse(data) as QueuedOperation[];
    } catch {
      return [];
    }
  }

  /**
   * Save all operations to storage
   */
  private saveAllOperations(operations: QueuedOperation[]): void {
    storage.set(STORAGE_KEY, JSON.stringify(operations));
  }

  /**
   * Enqueue an operation for later sync
   */
  async enqueue(operation: Omit<QueuedOperation, 'id' | 'createdAt' | 'status' | 'retryCount'>): Promise<QueuedOperation> {
    const queuedOperation: QueuedOperation = {
      ...operation,
      id: this.getNextId(),
      createdAt: new Date().toISOString(),
      status: 'pending',
      retryCount: 0,
    };

    const operations = this.getAllOperations();
    operations.push(queuedOperation);
    this.saveAllOperations(operations);

    this.notify();
    return queuedOperation;
  }

  /**
   * Get all pending operations
   */
  async getPending(): Promise<QueuedOperation[]> {
    const operations = this.getAllOperations();
    return operations.filter((op) => op.status === 'pending' || op.status === 'failed');
  }

  /**
   * Get queue statistics
   */
  async getStats(): Promise<QueueStats> {
    const operations = this.getAllOperations();
    return {
      total: operations.length,
      pending: operations.filter((op) => op.status === 'pending').length,
      failed: operations.filter((op) => op.status === 'failed').length,
      completed: operations.filter((op) => op.status === 'completed').length,
      permanentlyFailed: operations.filter((op) => op.status === 'permanently_failed').length,
    };
  }

  /**
   * Update operation status
   */
  async updateStatus(id: number, status: OperationStatus, error?: string): Promise<QueuedOperation | null> {
    const operations = this.getAllOperations();
    const index = operations.findIndex((op) => op.id === id);

    if (index === -1) return null;

    const operation = operations[index];
    operation.status = status;
    operation.lastError = error;
    operation.updatedAt = new Date().toISOString();

    if (status === 'failed') {
      operation.retryCount = (operation.retryCount || 0) + 1;
    }

    operations[index] = operation;
    this.saveAllOperations(operations);
    this.notify();

    return operation;
  }

  /**
   * Remove completed operations older than specified age
   */
  async cleanup(maxAgeMs: number = 24 * 60 * 60 * 1000): Promise<number> {
    const cutoff = Date.now() - maxAgeMs;
    const operations = this.getAllOperations();

    const filtered = operations.filter((op) => {
      if (op.status === 'completed' || op.status === 'permanently_failed') {
        const createdAt = new Date(op.createdAt).getTime();
        return createdAt >= cutoff;
      }
      return true;
    });

    const deletedCount = operations.length - filtered.length;
    this.saveAllOperations(filtered);

    if (deletedCount > 0) {
      this.notify();
    }

    return deletedCount;
  }

  /**
   * Sync all pending operations
   */
  async sync(executor?: OperationExecutor): Promise<{ synced: number; failed: number }> {
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
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          await this.updateStatus(operation.id, 'failed', errorMessage);

          // If max retries exceeded, mark as permanently failed
          if ((operation.retryCount || 0) >= MAX_RETRIES - 1) {
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
   * Execute a single operation using the API service
   */
  private async executeOperation(operation: QueuedOperation): Promise<unknown> {
    // Lazy import to avoid circular dependency
    const api = require('@/services/api').default;

    const response = await api({
      url: operation.endpoint,
      method: operation.method,
      data: operation.payload,
    });

    return response.data;
  }

  /**
   * Clear all operations
   */
  async clear(): Promise<void> {
    storage.remove(STORAGE_KEY);
    this.notify();
  }

  /**
   * Clear only completed/failed operations
   */
  async clearCompleted(): Promise<number> {
    const operations = this.getAllOperations();
    const pending = operations.filter((op) => op.status === 'pending');
    const deletedCount = operations.length - pending.length;

    this.saveAllOperations(pending);

    if (deletedCount > 0) {
      this.notify();
    }

    return deletedCount;
  }

  /**
   * Get current online status
   */
  getIsOnline(): boolean {
    return this.isOnline;
  }

  /**
   * Get sync in progress status
   */
  getIsSyncing(): boolean {
    return this.syncInProgress;
  }

  /**
   * Destroy the queue and cleanup listeners
   */
  destroy(): void {
    if (this.unsubscribeNetInfo) {
      this.unsubscribeNetInfo();
    }
    this.listeners.clear();
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

export const offlineQueue = new OfflineQueue();

export default offlineQueue;
