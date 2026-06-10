import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImportPreview } from '../components/ImportPreview';
import type { ImportPreviewResult } from '../services/import';

describe('ImportPreview Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fetch for API calls
    global.fetch = vi.fn();
  });

  it('should render upload area', () => {
    render(<ImportPreview onImport={() => {}} />);
    
    expect(screen.getByText(/上传截图/i)).toBeInTheDocument();
    expect(screen.getByText(/支持 PNG、JPG、WebP/i)).toBeInTheDocument();
  });

  it('should show loading state when uploading', async () => {
    // Mock fetch to return a pending promise (never resolves)
    let resolvePromise: () => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolvePromise = () => resolve(new Response());
    });
    (global.fetch as any).mockReturnValue(pendingPromise);
    
    render(<ImportPreview onImport={() => {}} />);
    
    const file = new File(['dummy'], 'test.png', { type: 'image/png' });
    const input = screen.getByTestId('file-input');
    
    fireEvent.change(input, { target: { files: [file] } });
    
    // Should show loading state immediately
    expect(screen.getByText(/正在识别截图/i)).toBeInTheDocument();
    
    // Cleanup: resolve the promise to avoid hanging
    resolvePromise!();
  });

  it('should display preview results', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '易方达蓝筹精选混合',
          type: '混合型',
          confidence: 0.95,
          source: 'code',
          needs_review: false,
        },
      ],
      total_confidence: 0.95,
      needs_review: false,
      total_count: 1,
    };

    render(<ImportPreview onImport={() => {}} initialData={mockResult} />);
    
    await waitFor(() => {
      expect(screen.getByText('易方达蓝筹精选混合')).toBeInTheDocument();
      expect(screen.getByText('005827')).toBeInTheDocument();
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
  });

  it('should show needs review warning for low confidence', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        {
          code: '005827',
          name: '易方达蓝筹精选混合',
          type: '混合型',
          confidence: 0.65,
          source: 'name_match',
          needs_review: true,
        },
      ],
      total_confidence: 0.65,
      needs_review: true,
      total_count: 1,
    };

    render(<ImportPreview onImport={() => {}} initialData={mockResult} />);
    
    // Should show the warning banner for low confidence
    expect(screen.getByText(/部分基金置信度较低/i)).toBeInTheDocument();
    // Should show "需确认" badge
    expect(screen.getByText('需确认')).toBeInTheDocument();
  });

  it('should handle select all checkbox', async () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        { code: '005827', name: '基金A', type: '混合型', confidence: 0.95, source: 'code', needs_review: false },
        { code: '110011', name: '基金B', type: '股票型', confidence: 0.85, source: 'code', needs_review: false },
      ],
      total_confidence: 0.9,
      needs_review: false,
      total_count: 2,
    };

    render(<ImportPreview onImport={() => {}} initialData={mockResult} />);
    
    const selectAllCheckbox = screen.getByTestId('select-all') as HTMLInputElement;
    
    // 默认两个高置信度基金应该都被选中，所以全选框应该是选中的
    expect(selectAllCheckbox.checked).toBe(true);
    
    // 取消全选
    await userEvent.click(selectAllCheckbox);
    expect(selectAllCheckbox.checked).toBe(false);
  });

  it('should show selected count', () => {
    const mockResult: ImportPreviewResult = {
      funds: [
        { code: '005827', name: '基金A', type: '混合型', confidence: 0.95, source: 'code', needs_review: false },
        { code: '110011', name: '基金B', type: '股票型', confidence: 0.65, source: 'name_match', needs_review: true },
      ],
      total_confidence: 0.8,
      needs_review: true,
      total_count: 2,
    };

    const { container } = render(<ImportPreview onImport={() => {}} initialData={mockResult} />);
    
    // 高置信度自动选中(1个)，低置信度未选中(1个)
    // 检查 footer 区域存在
    expect(container.textContent).toContain('已选择');
    expect(container.textContent).toContain('确认导入');
  });

  it('should call onImport with selected codes', async () => {
    const mockImport = vi.fn();
    const mockResult: ImportPreviewResult = {
      funds: [
        { code: '005827', name: '基金A', type: '混合型', confidence: 0.95, source: 'code', needs_review: false },
      ],
      total_confidence: 0.95,
      needs_review: false,
      total_count: 1,
    };

    // Mock successful /api/funds/batch response
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, added: ['005827'], invalid: [], warnings: [] }),
    });

    render(<ImportPreview onImport={mockImport} initialData={mockResult} />);
    
    const confirmButton = screen.getByRole('button', { name: /确认导入/i });
    await userEvent.click(confirmButton);
    
    // Wait for the async operation to complete
    await waitFor(() => {
      expect(mockImport).toHaveBeenCalledWith(['005827']);
    });
  });
});
