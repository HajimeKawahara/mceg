import { build, defineConfig } from 'vite';

const exportAsset = 'viewer-export.json';
const config = {
  base: './',
  build: {
    assetsInlineLimit: Infinity,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
  plugins: [{
    name: 'viewer-export',
    enforce: 'post', // Collect styles after Vite has emitted its CSS bundle.
    generateBundle(_, bundle) {
      const files = Object.values(bundle);
      const scripts = files.filter(file => file.type === 'chunk');
      if (scripts.length !== 1 || scripts[0].imports.length || scripts[0].dynamicImports.length) {
        this.error('HTML export requires one self-contained JavaScript bundle.');
      }
      const style = files.filter(file => file.fileName.endsWith('.css')).map(file => file.source).join('\n');
      if (!style.trim()) this.error('HTML export requires the viewer stylesheet.');
      this.emitFile({ type: 'asset', fileName: exportAsset, source: JSON.stringify({ script: scripts[0].code, style }) });
    },
    configureServer(server) {
      // Build on demand in development; production serves the emitted asset.
      server.middlewares.use(`/${exportAsset}`, async (_request, response, next) => {
        try {
          const result = await build({ ...config, configFile: false, root: server.config.root,
            logLevel: 'silent', build: { ...config.build, write: false } });
          response.setHeader('Content-Type', 'application/json');
          response.setHeader('Cache-Control', 'no-store');
          response.end(result.output.find(file => file.fileName === exportAsset).source);
        } catch (error) { next(error); }
      });
    },
  }],
};

export default defineConfig(config);
