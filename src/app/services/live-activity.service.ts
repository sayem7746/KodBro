import { Injectable } from '@angular/core';
import { Capacitor } from '@capacitor/core';

const ACTIVITY_ID = 'kodbro-agent';

@Injectable({ providedIn: 'root' })
export class LiveActivityService {
  private available: boolean | null = null;
  private lastUpdate = 0;
  private readonly throttleMs = 2000;

  async isAvailable(): Promise<boolean> {
    if (this.available !== null) return this.available;
    if (Capacitor.getPlatform() !== 'ios') {
      this.available = false;
      return false;
    }
    try {
      const { LiveActivity } = await import('capacitor-live-activity');
      const { value } = await LiveActivity.isAvailable();
      this.available = value;
      return value;
    } catch {
      this.available = false;
      return false;
    }
  }

  async start(appName: string): Promise<void> {
    if (!(await this.isAvailable())) return;
    try {
      const { LiveActivity } = await import('capacitor-live-activity');
      await LiveActivity.startActivity({
        id: ACTIVITY_ID,
        attributes: { appName },
        contentState: {
          title: 'KodBro',
          status: 'Starting…',
          message: appName || 'Building app',
        },
      });
    } catch (err) {
      console.warn('Live Activity start failed:', err);
    }
  }

  async update(status: string, message?: string): Promise<void> {
    if (!(await this.isAvailable())) return;
    const now = Date.now();
    if (now - this.lastUpdate < this.throttleMs) return;
    this.lastUpdate = now;
    try {
      const { LiveActivity } = await import('capacitor-live-activity');
      await LiveActivity.updateActivity({
        id: ACTIVITY_ID,
        contentState: {
          title: 'KodBro',
          status: status.slice(0, 50),
          message: (message || status).slice(0, 100),
        },
      });
    } catch (err) {
      console.warn('Live Activity update failed:', err);
    }
  }

  async end(status: string = 'Done', message?: string): Promise<void> {
    if (!(await this.isAvailable())) return;
    try {
      const { LiveActivity } = await import('capacitor-live-activity');
      await LiveActivity.endActivity({
        id: ACTIVITY_ID,
        contentState: {
          title: 'KodBro',
          status: status.slice(0, 50),
          message: (message || status).slice(0, 100),
        },
      });
    } catch (err) {
      console.warn('Live Activity end failed:', err);
    }
  }
}
