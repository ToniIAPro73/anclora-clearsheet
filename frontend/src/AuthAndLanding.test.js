import React from 'react';
import ReactDOMServer from 'react-dom/server';
import Landing from './components/Landing';
import Login from './components/Login';
import ActivateAccess from './components/ActivateAccess';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import { UIProvider } from './context/UIContext';

// Mock react-router-dom components and hooks for deterministic Jest SSR testing
jest.mock('react-router-dom', () => ({
  Link: ({ to, children, className, ...props }) => (
    <a href={to} className={className} {...props}>
      {children}
    </a>
  ),
  Navigate: ({ to }) => <div data-testid="navigate-redirect" data-to={to} />,
  useNavigate: () => () => {},
  useSearchParams: () => [new URLSearchParams(), () => {}],
  BrowserRouter: ({ children }) => <div>{children}</div>,
  MemoryRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: ({ element }) => element,
}));

describe('CleanSheet Frontend Public Surfaces & Auth Access Control', () => {
  test('Landing renders unauthenticated public surface with brand and clean copy', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <UIProvider>
          <Landing />
        </UIProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('CleanSheet');
    expect(html).toContain('brand/anclora-clearsheet.png');
    // Must contain Sign in or Iniciar sesión
    expect(html).toMatch(/Iniciar sesión|Sign in/);
    // Must contain Activate access CTA
    expect(html).toMatch(/Activar acceso|Activate access/);
    // MUST NOT contain social login buttons or free registration
    expect(html).not.toContain('Google');
    expect(html).not.toContain('GitHub');
    expect(html).not.toContain('Crear cuenta gratis');
    expect(html).not.toContain('Sign up for free');
  });

  test('Login page renders dedicated email/password form without social login or free registration', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <UIProvider>
          <Login />
        </UIProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('data-testid="login-email-input"');
    expect(html).toContain('data-testid="login-password-input"');
    expect(html).toContain('data-testid="login-submit-button"');
    expect(html).toContain('data-testid="login-password-toggle"');
    // Link to activation
    expect(html).toMatch(/Activar acceso|Activate access/);
    // STRICT: No social login buttons
    expect(html).not.toContain('auth-social');
    expect(html).not.toContain('Google');
    expect(html).not.toContain('GitHub');
    expect(html).not.toContain('oauth');
    // STRICT: No free registration
    expect(html).not.toContain('Crear cuenta');
    expect(html).not.toContain('Register');
    expect(html).not.toContain('Sign up');
  });

  test('ActivateAccess renders invitation token validation interface', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <UIProvider>
          <ActivateAccess />
        </UIProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('data-testid="activation-token-input"');
    expect(html).toContain('data-testid="activation-token-submit"');
    expect(html).toMatch(/Token de Invitación|Invitation Token/);
  });

  test('ProtectedRoute blocks unauthenticated access without rendering children', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <ProtectedRoute>
          <div data-testid="secret-workspace">Sensitive Workspace Data</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    // Initial unauth state must not leak sensitive workspace content
    expect(html).not.toContain('Sensitive Workspace Data');
  });

  test('No free registration or social login exists across any public view', () => {
    const views = [
      <AuthProvider><UIProvider><Landing /></UIProvider></AuthProvider>,
      <AuthProvider><UIProvider><Login /></UIProvider></AuthProvider>,
      <AuthProvider><UIProvider><ActivateAccess /></UIProvider></AuthProvider>
    ];

    views.forEach((view) => {
      const html = ReactDOMServer.renderToString(view);
      expect(html).not.toContain('oauth_identities');
      expect(html).not.toContain('social_login');
      expect(html).not.toContain('btn-google');
      expect(html).not.toContain('btn-github');
      expect(html).not.toContain('free-registration');
    });
  });
});
