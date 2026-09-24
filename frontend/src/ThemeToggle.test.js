import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { UIProvider, useUI } from './context/UIContext';
import ThemeToggle from './components/ThemeToggle';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  localStorage.clear();
  window.matchMedia = jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  }));
});

describe('ThemeToggle Direct Cycle (CleanSheet)', () => {
  let container = null;
  let root = null;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    container = null;
  });

  test('cycles directly dark -> light -> system -> dark on click without dropdown menu', () => {
    let currentUI = null;
    const TestConsumer = () => {
      currentUI = useUI();
      return <ThemeToggle />;
    };

    act(() => {
      root.render(
        <UIProvider>
          <TestConsumer />
        </UIProvider>
      );
    });

    const button = container.querySelector('[data-testid="theme-toggle-button"]');
    expect(button).toBeTruthy();
    expect(button.getAttribute('type')).toBe('button');
    expect(button.getAttribute('aria-expanded')).toBeNull();
    expect(button.getAttribute('aria-haspopup')).toBeNull();
    expect(button.className).toContain('h-9');
    expect(button.className).toContain('w-9');

    // Initial theme: dark
    expect(currentUI.theme).toBe('dark');
    expect(container.querySelector('[data-testid="theme-dropdown-menu"]')).toBeNull();
    expect(container.querySelector('[data-testid="theme-option-dark"]')).toBeNull();
    expect(container.querySelector('[data-testid="theme-option-light"]')).toBeNull();
    expect(container.querySelector('[data-testid="theme-option-system"]')).toBeNull();
    expect(localStorage.getItem('cleansheet_theme')).toBe('dark');

    // Click 1 -> light
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('light');
    expect(container.querySelector('[data-testid="theme-dropdown-menu"]')).toBeNull();
    expect(localStorage.getItem('cleansheet_theme')).toBe('light');

    // Click 2 -> system
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('system');
    expect(container.querySelector('[data-testid="theme-dropdown-menu"]')).toBeNull();
    expect(localStorage.getItem('cleansheet_theme')).toBe('system');

    // Click 3 -> dark
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('dark');
    expect(container.querySelector('[data-testid="theme-dropdown-menu"]')).toBeNull();
    expect(localStorage.getItem('cleansheet_theme')).toBe('dark');
  });

  test('preserves initial light and system states when cycling', () => {
    localStorage.setItem('cleansheet_theme', 'light');
    let currentUI = null;
    const TestConsumer = () => {
      currentUI = useUI();
      return <ThemeToggle />;
    };

    act(() => {
      root.render(
        <UIProvider>
          <TestConsumer />
        </UIProvider>
      );
    });

    const button = container.querySelector('[data-testid="theme-toggle-button"]');
    expect(currentUI.theme).toBe('light');

    // light -> system
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('system');
    expect(localStorage.getItem('cleansheet_theme')).toBe('system');

    // system -> dark
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('dark');
    expect(localStorage.getItem('cleansheet_theme')).toBe('dark');

    // dark -> light
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(currentUI.theme).toBe('light');
    expect(localStorage.getItem('cleansheet_theme')).toBe('light');
  });
});
