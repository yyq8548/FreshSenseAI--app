import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {TechStack} from '../src/components/TechStack';

describe('FreshSense technology card', () => {
  it('names the six implemented platform technologies', () => {
    const markup = renderToStaticMarkup(<TechStack />);
    for (const name of ['Python', 'TensorFlow', 'FastAPI', 'React', 'PostgreSQL', 'Azure']) {
      expect(markup).toContain(name);
    }
  });
});
