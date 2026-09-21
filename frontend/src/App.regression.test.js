import React from 'react';
import ReactDOMServer from 'react-dom/server';
import RecipesView from './components/RecipesView';
import BatchProcessingView from './components/BatchProcessingView';
import { translations } from './i18n';

describe('Regression Tests: RecipesView & BatchProcessingView server-side rendering', () => {
  test('RecipesView renders initial loading state without throwing errors', () => {
    const html = ReactDOMServer.renderToString(
      <RecipesView t={translations.es} onSelectRecipeForReapplication={() => {}} />
    );
    expect(html).toBeDefined();
    expect(html).toContain("lucide-loader-circle");
  });

  test('BatchProcessingView renders header and batch container cleanly', () => {
    const html = ReactDOMServer.renderToString(
      <BatchProcessingView t={translations.es} openAuthModal={() => {}} />
    );
    expect(html).toBeDefined();
    expect(html).toContain("Procesamiento por Lotes");
    expect(html).toContain("Inspector de Lotes Históricos");
    expect(html).toContain("no-past-batches-notice");
  });

  test('ConnectorsView renders cloud storage header and new connector button', () => {
    const ConnectorsView = require('./components/ConnectorsView').default;
    const html = ReactDOMServer.renderToString(
      <ConnectorsView t={translations.es} openAuthModal={() => {}} />
    );
    expect(html).toBeDefined();
    expect(html).toContain("Conectores Cloud");
    expect(html).toContain("Nuevo Conector S3");
    expect(html).toContain("Ejecutor Pipeline Cloud");
  });

  test('SchedulesView renders scheduled automations header and new schedule button', () => {
    const SchedulesView = require('./components/SchedulesView').default;
    const html = ReactDOMServer.renderToString(
      <SchedulesView t={translations.es} openAuthModal={() => {}} />
    );
    expect(html).toBeDefined();
    expect(html).toContain("Automatizaciones Programadas");
    expect(html).toContain("Nueva Automatización Programada");
  });
});
