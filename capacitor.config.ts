import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'io.kodbro.app',
  appName: 'KodBro',
  webDir: 'www',
  server: {
    androidScheme: 'https',
  },
};

export default config;
