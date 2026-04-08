import { API_BASE_URL } from './config';

export interface ImportPreviewItem {
  code: string;
  name: string;
  type: string;
  confidence: number;
  source: 'code' | 'name_match' | 'table';
  needs_review: boolean;
}

export interface ImportPreviewResult {
  funds: ImportPreviewItem[];
  total_confidence: number;
  needs_review: boolean;
  total_count: number;
}

export interface ImportConfirmResult {
  success: boolean;
  added: number;
  total: number;
  invalid: string[];
}

/**
 * Upload image and get import preview
 */
export async function previewImport(file: File): Promise<ImportPreviewResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/import/preview`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to preview import');
  }

  return response.json();
}

/**
 * Confirm import of selected funds
 */
export async function confirmImport(codes: string[]): Promise<ImportConfirmResult> {
  const response = await fetch(`${API_BASE_URL}/api/import/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ codes }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to confirm import');
  }

  return response.json();
}

/**
 * AI-assisted import (placeholder)
 */
export async function aiImport(file: File): Promise<ImportPreviewResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/import/ai`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process AI import');
  }

  return response.json();
}

/**
 * Format confidence as percentage string
 */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get confidence color based on value
 */
export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'text-green-600';
  if (confidence >= 0.75) return 'text-yellow-600';
  return 'text-red-600';
}

/**
 * Get confidence badge variant
 */
export function getConfidenceBadge(confidence: number): {
  label: string;
  className: string;
} {
  if (confidence >= 0.85) {
    return { label: '高置信度', className: 'bg-green-100 text-green-800' };
  }
  if (confidence >= 0.75) {
    return { label: '中置信度', className: 'bg-yellow-100 text-yellow-800' };
  }
  return { label: '需确认', className: 'bg-red-100 text-red-800' };
}
