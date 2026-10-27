import { defineConfig } from 'vite';
import { resolve } from 'node:path';
export default defineConfig({build:{rollupOptions:{input:{background:resolve('src/background.ts'),popup:resolve('popup.html'),blocked:resolve('blocked.html'),options:resolve('options.html')},output:{entryFileNames:'[name].js',chunkFileNames:'chunks/[name].js'}}}});
