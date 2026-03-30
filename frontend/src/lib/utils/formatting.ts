/**
 * Formatting Utilities
 * Shared formatting functions used across components
 */

/**
 * Get initials from a name
 * @param name - Full name
 * @returns Initials (2 characters)
 */
export const getInitials = (name: string | null | undefined): string => {
  if (!name) return '?';
  const parts = name.trim().split(' ').filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
};

/**
 * Format phone number for WhatsApp link
 * @param phone - Phone number
 * @returns Full WhatsApp URL (https://wa.me/62xxx)
 */
export const formatPhoneForWhatsApp = (phone: string | null | undefined): string => {
  if (!phone) return '#';
  // Remove all non-digit characters except +
  let cleaned = phone.replace(/[^\d+]/g, '');
  // Remove leading + for WhatsApp
  if (cleaned.startsWith('+')) {
    cleaned = cleaned.substring(1);
  }
  // Add Indonesia country code if starts with 0
  if (cleaned.startsWith('0')) {
    cleaned = '62' + cleaned.substring(1);
  }
  return `https://wa.me/${cleaned}`;
};

/**
 * Capitalize first letter of each word
 * @param str - Input string
 * @returns Title cased string
 */
export const toTitleCase = (str: string | null | undefined): string => {
  if (!str) return '';
  return str
    .toLowerCase()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Truncate text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text
 */
export const truncateText = (text: string | null | undefined, maxLength = 50): string => {
  if (!text || text.length <= maxLength) return text || '';
  return text.substring(0, maxLength - 3) + '...';
};

/**
 * Format currency (Indonesian Rupiah)
 * @param amount - Amount in IDR
 * @returns Formatted currency string
 */
export const formatCurrency = (amount: number | null | undefined): string => {
  if (amount == null) return 'Rp 0';
  return `Rp ${amount.toLocaleString('id-ID')}`;
};
